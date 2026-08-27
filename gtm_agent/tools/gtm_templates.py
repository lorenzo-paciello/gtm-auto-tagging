"""Community and custom template support.

Template-backed tags ARE creatable through the Tag Manager API. The trap is the
tag type string, and it differs by where the template came from. Verified
against the live API with the real Meta, TikTok and Pinterest gallery
templates:

    Gallery template   ->  cvt_<galleryTemplateId>            e.g. cvt_MRQN8
    Custom template    ->  cvt_<containerId>_<templateId>     e.g. cvt_261951688_49

Getting it wrong produces

    400 vendorTemplate.key: Unknown entity type (template public ID: cvt_261951688_54)

which reads like "the API does not support community templates" and is really
"that type string does not exist". Do not construct it from parts. Every
template declares its own public id in the `___INFO___` section of its
`templateData`, and `resolve_tag_type` reads it from there:

    Pinterest  galleryTemplateId=NGMPN  ___INFO___.id = "cvt_NGMPN"
    Meta       galleryTemplateId=5RM3Q  ___INFO___.id = "cvt_5RM3Q"
    TikTok     galleryTemplateId=MRQN8  ___INFO___.id = "cvt_MRQN8"

A custom template written by hand carries the placeholder `cvt_temp_public_id`
instead; GTM assigns it `cvt_<containerId>_<templateId>` at save time, so that
is the fallback.

Templates also declare their own parameters. The API enforces the ones marked
`NON_EMPTY` -- but many vendor templates mark nothing required, so a TikTok tag
with no `pixel_code` is accepted and does nothing. Parsing the contract out of
`templateData` is the only way to know what a given template actually accepts:
the names are vendor-specific (`pixelId`, `pixel_code`, `tagId`) and not
guessable.
"""

from __future__ import annotations

import json
import re
from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import paginate
from .gtm_client import tool_errors
from .gtm_client import workspaces

#: `templateData` is the .tpl file format: named sections separated by
#: ___SECTION_NAME___ markers.
_SECTION_PATTERN = re.compile(r"^___([A-Z0-9_]+)___\s*$", re.MULTILINE)

#: Parameter container types whose real fields live in `subParams`.
_GROUPING_TYPES = {"GROUP"}

#: Presentational entries that are not API parameters at all. Vendor templates
#: use them for help text, and some carry names with spaces.
_PRESENTATIONAL_TYPES = {"LABEL"}

#: The placeholder id a hand-written template carries before GTM assigns one.
_PLACEHOLDER_TEMPLATE_ID = "cvt_temp_public_id"

#: Vendor help text is written for the GTM UI and often contains markup.
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _localized_text(value: Any) -> Optional[str]:
    """Return the display string of a field that may be localized.

    A translated template declares user-facing text as
    `{"text": "Bundle URL", "translations": [{"locale": "tr", ...}]}` rather
    than a plain string. Passing that through raw put a Python dict repr into
    the error messages the agent reads back:

        `bundleURL` ({'text': 'Bundle URL', 'translations': [...]}) is required

    One template can carry dozens of these.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        text = value.get("text")
        return str(text) if text is not None else None
    return str(value)


def _strip_html(text: str) -> str:
    """Flatten vendor help text into something readable in a tool result."""
    return _WHITESPACE_PATTERN.sub(" ", _HTML_TAG_PATTERN.sub(" ", text)).strip()


def _split_sections(template_data: str) -> dict[str, str]:
    """Split a .tpl document into its ___SECTION___ blocks."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_PATTERN.finditer(template_data or ""))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(template_data)
        sections[match.group(1)] = template_data[match.end() : end].strip()
    return sections


def _flatten_parameters(
    params: list[dict[str, Any]], prefix: str = ""
) -> list[dict[str, Any]]:
    """Flatten a template parameter tree into the keys the API accepts."""
    flat: list[dict[str, Any]] = []
    for param in params or []:
        name = param.get("name")
        if not name:
            continue

        param_type = param.get("type", "")
        if param_type in _GROUPING_TYPES:
            # A GROUP is presentational: its subParams are the real API keys.
            flat.extend(_flatten_parameters(param.get("subParams", []), prefix))
            continue
        if param_type in _PRESENTATIONAL_TYPES:
            # Help text, not a parameter. Vendor templates are full of these.
            continue

        validators = param.get("valueValidators") or []
        required = any(v.get("type") == "NON_EMPTY" for v in validators)

        entry: dict[str, Any] = {
            "name": f"{prefix}{name}",
            "display_name": _localized_text(param.get("displayName")),
            "type": param_type,
            "required": required,
            "default_value": param.get("defaultValue"),
        }

        # A template the agent has never seen has to be self-describing, and
        # these are the fields the vendor wrote for a human reading the UI.
        for source, target in (
            ("help", "help"),
            ("valueHint", "value_hint"),
            ("checkboxText", "checkbox_text"),
            ("notSetText", "not_set_text"),
        ):
            text = _localized_text(param.get(source))
            if text:
                entry[target] = _strip_html(text)[:400]
        if param.get("macrosInSelect"):
            entry["accepts_variable"] = True

        # Templates validate format, not just presence. Meta rejects a pixel id
        # that is not digits; Pinterest rejects a tag id that is not 26 + 11
        # digits. Surfacing these turns a 400 into a checkable constraint.
        for validator in validators:
            vtype = validator.get("type")
            args = validator.get("args") or []
            message = validator.get("errorMessage")
            if vtype == "REGEX" and args:
                entry["pattern"] = args[0]
                if message:
                    entry["pattern_error"] = message
            elif vtype == "STRING_LENGTH" and len(args) >= 2:
                entry["min_length"], entry["max_length"] = args[0], args[1]
                if message:
                    entry["length_error"] = message
            elif vtype in ("NUMBER", "POSITIVE_NUMBER", "NON_NEGATIVE_NUMBER"):
                entry["must_be_number"] = True
                entry["number_constraint"] = vtype
        # SELECT keeps its options under `selectItems`, RADIO under
        # `radioItems`. Reading only the first silently drops the valid values
        # of every radio parameter, which is how an agent ends up inventing one.
        choices = param.get("selectItems") or param.get("radioItems")
        if choices:
            entry["allowed_values"] = [
                {
                    "value": item.get("value"),
                    "label": _localized_text(item.get("displayValue")),
                }
                for item in choices
            ]
        if param_type in ("PARAM_TABLE", "SIMPLE_TABLE"):
            columns = param.get("paramTableColumns") or param.get("simpleTableColumns") or []
            entry["table_columns"] = [
                (c.get("param", {}).get("name") if "param" in c else c.get("name"))
                for c in columns
            ]
            entry["note"] = (
                "Table parameter: pass a JSON list of objects keyed by the "
                "column names above."
            )
        if param.get("enablingConditions"):
            entry["only_applies_when"] = [
                f"{c.get('paramName')} {c.get('type', '').lower()} {c.get('paramValue')}"
                for c in param["enablingConditions"]
            ]
        flat.append(entry)
    return flat


def _parse_info(template_data: str) -> dict[str, Any]:
    """Return the parsed `___INFO___` block, or an empty dict."""
    sections = _split_sections(template_data)
    if "INFO" not in sections:
        return {}
    try:
        return json.loads(sections["INFO"])
    except json.JSONDecodeError:
        return {}


#: A template that injects a script and reaches a vendor host loads the pixel
#: library itself. One that only reads and calls window globals depends on some
#: other tag having loaded it first.
_SCRIPT_INJECTION_MARKERS = ("inject_script", "injectScript")


def template_bootstraps_library(template: dict[str, Any]) -> bool:
    """Can this template's tags run without a separate base tag already loaded?

    Verified against the three official templates:

    * Meta      -- injects connect.facebook.net/en_US/fbevents.js, calls
                   fbq('init', pixelId). Self-bootstrapping.
    * Pinterest -- injects s.pinimg.com/ct/core.js, calls pintrk('load', tagId).
                   Self-bootstrapping.
    * TikTok    -- no inject_script permission, no vendor URL; it only calls
                   into an existing `ttq`. NOT self-bootstrapping, so an event
                   tag without a base tag does nothing.

    This decides whether a missing setup tag is fatal or merely costly, which
    is the difference between "no data at all" and "no page-view coverage".
    """
    data = template.get("templateData", "") or ""
    sections = _split_sections(data)
    blob = sections.get("WEB_PERMISSIONS", "") + sections.get(
        "SANDBOXED_JS_FOR_WEB_TEMPLATE", ""
    )
    return any(marker in blob for marker in _SCRIPT_INJECTION_MARKERS)


#: Parameters whose name contains "event" but which are not the event NAME.
#: A dedup id is not what a tag is measuring.
_NON_EVENT_PARAM_NAMES = {"eventid", "eventidentifier", "eventuuid"}

#: Suffixes that mark a parameter as an account / pixel identifier.
_ID_PARAM_SUFFIXES = ("id", "code", "key")


def _looks_like_id_parameter(name: str) -> bool:
    lowered = name.lower().replace("_", "")
    if lowered == "id":
        return True
    if lowered.startswith("visitor") or lowered.startswith("user"):
        return False  # a visitor id identifies the person, not the account
    return lowered.endswith(_ID_PARAM_SUFFIXES)


def template_role_hints(parameters: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive, from a template's own parameters, how to read tags built on it.

    Hardcoding these per vendor does not survive contact with reality: Snapchat
    names its event `eventName`, Reddit uses `eventType`, Pinterest has both
    `eventName` and `adeEventName`, and Criteo's loader declares no event at
    all. The template already states its own contract, so read it instead of
    guessing.

    `declares_events=False` is the useful signal for loader templates: a
    template with no event parameter can only produce base tags.

    Args:
        parameters: the flattened output of `parse_template_parameters`.

    Returns:
        `event_parameters`, `id_parameters` (most likely first) and
        `declares_events`.
    """
    event_parameters = [
        p["name"]
        for p in parameters
        if "event" in p["name"].lower()
        and p["name"].lower().replace("_", "") not in _NON_EVENT_PARAM_NAMES
    ]

    candidates = [p for p in parameters if _looks_like_id_parameter(p["name"])]
    # A required identifier is the account id; an optional one may be anything.
    id_parameters = [p["name"] for p in candidates if p.get("required")] + [
        p["name"] for p in candidates if not p.get("required")
    ]

    return {
        "event_parameters": event_parameters,
        "id_parameters": id_parameters,
        "declares_events": bool(event_parameters),
        # Zero parameters means the template declared none OR we failed to
        # parse it. Callers must not read "no event parameter" as "loader"
        # without checking this first.
        "parameter_count": len(parameters),
    }


def resolve_tag_type(template: dict[str, Any]) -> str:
    """Return the tag type string `create_tag` must use for this template.

    A template declares its own public id in `___INFO___.id`. That is the
    authoritative value:

        gallery template  ->  cvt_<galleryTemplateId>          (e.g. cvt_MRQN8)
        custom template   ->  cvt_<containerId>_<templateId>

    Never assemble this from parts. A gallery template given the custom-template
    shape produces `400 Unknown entity type`, which is easy to misread as the
    API refusing community templates.

    Args:
        template: a template resource as returned by `templates().list/get`.
    """
    declared = _parse_info(template.get("templateData", "")).get("id")
    if declared and declared != _PLACEHOLDER_TEMPLATE_ID:
        return declared

    gallery_id = (template.get("galleryReference") or {}).get("galleryTemplateId")
    if gallery_id:
        return f"cvt_{gallery_id}"

    return f"cvt_{template.get('containerId')}_{template.get('templateId')}"


def parse_template_parameters(template_data: str) -> dict[str, Any]:
    """Extract the parameter contract from a template's `templateData`."""
    sections = _split_sections(template_data)
    info = _parse_info(template_data)

    parameters: list[dict[str, Any]] = []
    parse_error: Optional[str] = None
    if "TEMPLATE_PARAMETERS" in sections:
        try:
            parameters = _flatten_parameters(json.loads(sections["TEMPLATE_PARAMETERS"]))
        except json.JSONDecodeError as exc:
            parse_error = f"Could not parse ___TEMPLATE_PARAMETERS___: {exc}"

    return {
        "declared_id": info.get("id"),
        "display_name": _localized_text(info.get("displayName")),
        "description": _localized_text(info.get("description")),
        "container_contexts": info.get("containerContexts", []),
        "parameters": parameters,
        "required_parameters": [p["name"] for p in parameters if p["required"]],
        "sections_present": sorted(sections),
        "parse_error": parse_error,
    }


@tool_errors
def list_templates(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """List the custom / community templates installed in the workspace.

    Third-party pixels (Meta, TikTok, Pinterest, LinkedIn) are almost always
    community templates. This is how you get the tag type to pass to
    `create_tag`.

    Use the `tag_type` field EXACTLY as returned. Do NOT assemble it yourself:
    a gallery template uses `cvt_<galleryTemplateId>` (e.g. `cvt_MRQN8`) while a
    hand-written custom template uses `cvt_<containerId>_<templateId>`. Applying
    the wrong shape returns `400 Unknown entity type`, which looks like the API
    refusing community templates when it is really rejecting a type that does
    not exist.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `templates` (templateId, name, the `tag_type` to use, the
        gallery owner/repository when installed from the Community Template
        Gallery, and the required parameter names).
    """
    acc, cont, ws = settings.resolve_context(account_id, container_id, workspace_id)
    parent = f"accounts/{acc}/containers/{cont}/workspaces/{ws}"
    items = paginate(workspaces().templates(), "list", "template", parent=parent)

    templates = []
    for item in items:
        gallery = item.get("galleryReference") or {}
        parsed = parse_template_parameters(item.get("templateData", ""))
        templates.append(
            {
                "templateId": item.get("templateId"),
                "name": item.get("name"),
                "tag_type": resolve_tag_type(item),
                "source": "gallery" if gallery else "custom",
                "gallery_owner": gallery.get("owner"),
                "gallery_repository": gallery.get("repository"),
                "gallery_version": gallery.get("version"),
                "is_modified": gallery.get("isModified"),
                "required_parameters": parsed["required_parameters"],
            }
        )

    return {
        "parent": parent,
        "count": len(templates),
        "templates": templates,
        "note": (
            "Pass `tag_type` verbatim to create_tag -- never rebuild it. Call "
            "`get_template_spec` for the full parameter contract before "
            "building parameters_json: many vendor templates mark nothing as "
            "required, so a tag missing the account id is accepted silently."
        ),
    }


@tool_errors
def get_template_spec(
    template_id: str,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Read a template's parameter contract: what `create_tag` must send.

    Community templates declare their own parameters. The names are
    vendor-specific and not guessable -- Meta uses `pixelId`, TikTok uses
    `pixel_code`, Pinterest uses `tagId` -- so read them here instead of
    guessing.

    Note that `required_parameters` reflects only what the template marks as
    NON_EMPTY, which the API enforces. Many vendor templates mark nothing: the
    TikTok Pixel template accepts a tag with no `pixel_code` at all, creating a
    tag that looks fine and sends nothing. Treat the account-id parameter as
    mandatory regardless of what this reports.

    Args:
        template_id: numeric template id, from `list_templates`.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The `tag_type` to pass to `create_tag`, every parameter the template
        accepts (name, display name, type, required, allowed values, table
        columns), and the required subset.
    """
    acc, cont, ws = settings.resolve_context(account_id, container_id, workspace_id)
    parent = f"accounts/{acc}/containers/{cont}/workspaces/{ws}"
    path = f"{parent}/templates/{template_id}"

    template = workspaces().templates().get(path=path).execute()
    gallery = template.get("galleryReference") or {}
    parsed = parse_template_parameters(template.get("templateData", ""))

    return {
        "templateId": template.get("templateId"),
        "name": template.get("name"),
        "tag_type": resolve_tag_type(template),
        "source": "gallery" if gallery else "custom",
        "display_name": parsed["display_name"],
        "description": parsed["description"],
        "gallery_owner": gallery.get("owner"),
        "gallery_repository": gallery.get("repository"),
        "is_modified": gallery.get("isModified"),
        "container_contexts": parsed["container_contexts"],
        "required_parameters": parsed["required_parameters"],
        "parameters": parsed["parameters"],
        "parse_error": parsed["parse_error"],
        "note": (
            "Pass `tag_type` verbatim to create_tag. Parameters marked required "
            "are enforced by the API. An EMPTY required_parameters list does "
            "NOT mean the tag works without configuration -- it means this "
            "template validates nothing, so you must supply the account id "
            "yourself."
        ),
    }


def resolve_installed_template(
    tag_type: str,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Find the installed template a `cvt_` tag type refers to, if any.

    Matches against each template's real public id rather than parsing the
    string, because the two shapes (`cvt_MRQN8` for gallery, `cvt_<container>_
    <template>` for custom) cannot be told apart reliably by pattern alone.

    Used by `create_tag` to validate template-backed tags before sending, and to
    give an actionable error when the type does not match anything installed.

    Returns:
        The parsed spec for the matching template, or None.
    """
    if not (tag_type or "").startswith("cvt_"):
        return None

    acc, cont, ws = settings.resolve_context(account_id, container_id, workspace_id)
    parent = f"accounts/{acc}/containers/{cont}/workspaces/{ws}"
    items = paginate(workspaces().templates(), "list", "template", parent=parent)

    for item in items:
        if resolve_tag_type(item) == tag_type:
            gallery = item.get("galleryReference") or {}
            parsed = parse_template_parameters(item.get("templateData", ""))
            return {
                "templateId": item.get("templateId"),
                "name": item.get("name"),
                "tag_type": tag_type,
                "source": "gallery" if gallery else "custom",
                "required_parameters": parsed["required_parameters"],
                "parameters": parsed["parameters"],
            }
    return None


def installed_template_types(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> list[dict[str, str]]:
    """List `(name, tag_type)` for every installed template, for error messages."""
    acc, cont, ws = settings.resolve_context(account_id, container_id, workspace_id)
    parent = f"accounts/{acc}/containers/{cont}/workspaces/{ws}"
    items = paginate(workspaces().templates(), "list", "template", parent=parent)
    return [{"name": i.get("name"), "tag_type": resolve_tag_type(i)} for i in items]
