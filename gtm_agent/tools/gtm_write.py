"""WRITE tools for the GTM workspace (tags, triggers and variables).

Safety rules enforced here:

* Nothing is ever published. Changes land in the workspace (draft) and the user
  publishes manually from the GTM UI.
* No tool deletes an entity.
* With `GTM_DRY_RUN=true` in `.env`, these functions return the payload that
  would have been sent without calling the API.
"""

from __future__ import annotations

import json
import re
from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import paginate
from .gtm_client import parameters_to_dict
from .gtm_client import tool_errors
from .gtm_client import workspaces
import logging

from .gtm_creation_gate import conflicts_with_existing
from .gtm_templates import installed_template_types
from .gtm_templates import resolve_installed_template
from .gtm_templates import template_role_hints
from .references import check_references
from .references import extract_references
from .tag_specs import PARAMETER_TYPE_OVERRIDES
from .tag_specs import TAG_SPECS
from .tag_specs import TRIGGER_TYPES
from .tag_specs import format_problems
from .tag_specs import validate_entity

logger = logging.getLogger(__name__)

_ENTITY_RESOURCES = {
    "tag": ("tags", "tagId"),
    "trigger": ("triggers", "triggerId"),
    "variable": ("variables", "variableId"),
    "folder": ("folders", "folderId"),
}


# ---------------------------------------------------------------------------
# Flat configuration -> GTM API `parameter` format
# ---------------------------------------------------------------------------


def _to_parameter(
    value: Any, key: Optional[str] = None, forced_type: Optional[str] = None
) -> dict[str, Any]:
    """Convert a Python value into the `Parameter` object the API expects."""
    param: dict[str, Any] = {}
    if key is not None:
        param["key"] = key

    # Explicit escape hatch: {"__type__": "tagReference", "value": "Tag name"}
    if isinstance(value, dict) and "__type__" in value:
        param["type"] = value["__type__"]
        param["value"] = str(value.get("value", ""))
        return param

    if forced_type:
        param["type"] = forced_type
        param["value"] = "" if value is None else str(value)
        return param

    if isinstance(value, bool):
        param["type"] = "boolean"
        param["value"] = "true" if value else "false"
    elif isinstance(value, int):
        param["type"] = "integer"
        param["value"] = str(value)
    elif isinstance(value, dict):
        param["type"] = "map"
        param["map"] = [_to_parameter(v, k) for k, v in value.items()]
    elif isinstance(value, list):
        param["type"] = "list"
        param["list"] = [_to_parameter(item) for item in value]
    else:
        param["type"] = "template"
        param["value"] = "" if value is None else str(value)
    return param


def to_gtm_parameters(
    flat_config: dict[str, Any], entity_type: str = ""
) -> list[dict[str, Any]]:
    """Convert `{"key": value}` into the GTM API `parameter` list.

    Some parameters must carry a non-`template` type that a flat JSON string
    cannot express -- `gaawe.measurementId` has to be a `tagReference` naming
    another tag. Those are applied automatically from the spec registry.
    """
    overrides = PARAMETER_TYPE_OVERRIDES.get(entity_type, {})
    return [
        _to_parameter(value, key, overrides.get(key))
        for key, value in flat_config.items()
    ]


def _load_json_arg(raw: str, arg_name: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"`{arg_name}` is not valid JSON: {exc}. "
            'Expected something like: {"tagId": "G-XXXX", "eventName": "purchase"}'
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"`{arg_name}` must be a JSON object, not {type(parsed).__name__}."
        )
    return parsed


#: Tag types that exist solely to run. One created without a firing trigger is
#: inert: it shows in the container, appears in the version diff, and never
#: executes. The API accepts it without comment.
_TAGS_THAT_MUST_FIRE = frozenset(TAG_SPECS) - {"html", "img"}


def _workspace_reference_context(
    account_id: Optional[str],
    container_id: Optional[str],
    workspace_id: Optional[str],
) -> tuple[list[str], list[str]]:
    """Names the workspace can resolve: user variables and enabled built-ins."""
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    ws = workspaces()
    variables = paginate(ws.variables(), "list", "variable", parent=parent)
    built_ins = paginate(
        ws.built_in_variables(), "list", "builtInVariable", parent=parent
    )
    return (
        [v.get("name") for v in variables if v.get("name")],
        [b.get("name") for b in built_ins if b.get("name")],
    )


def _reference_problems(
    config: dict[str, Any],
    account_id: Optional[str],
    container_id: Optional[str],
    workspace_id: Optional[str],
) -> list[dict[str, str]]:
    """Check every `{{Name}}` in a payload against what the workspace can resolve."""
    if not extract_references(config):
        return []
    variables, built_ins = _workspace_reference_context(
        account_id, container_id, workspace_id
    )
    return check_references(config, variables, built_ins)


def _trigger_problems(
    tag_type: str, firing_trigger_ids: Optional[list[str]], allow_no_trigger: bool
) -> list[dict[str, str]]:
    if firing_trigger_ids or allow_no_trigger or tag_type not in _TAGS_THAT_MUST_FIRE:
        return []
    return [
        {
            "severity": "error",
            "message": (
                f"`{tag_type}` tag created with no firing trigger. It would "
                "never execute."
            ),
            "fix": (
                "Pass `firing_trigger_ids`. Built-in ids: 2147479553 (All "
                "Pages), 2147479573 (Initialization), 2147479572 (Consent "
                "Initialization); `list_triggers` has the workspace ones. If "
                "this tag is deliberately fired only by tag sequencing from "
                "another tag, pass allow_no_trigger=True."
            ),
        }
    ]


def _duplicate_gate(
    tag_type: str,
    config: dict[str, Any],
    name: str,
    firing_trigger_ids: Optional[list[str]],
    confirm_duplicate: bool,
    account_id: Optional[str],
    container_id: Optional[str],
    workspace_id: Optional[str],
    exclude_tag_id: Optional[str] = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Refuse to write a tag that would duplicate one already in the workspace.

    This used to be a warning attached to the created tag, which got the order
    backwards: the user was told about the duplicate *after* it existed, and
    the cleanup was theirs. Governance means the question is asked first.

    Returns `(problems, report)`. A blocking conflict comes back with severity
    `error`, so `create_tag` returns it and writes nothing. The user sees what
    already exists, decides, and only then is `confirm_duplicate=True` passed
    -- which downgrades the same finding to a warning and lets the write
    through. The flag is the user's decision to record, never the agent's.

    A lookup failure must not block a write: an unreachable API would
    otherwise make the whole tool unusable. It degrades to no check, loudly.
    """
    try:
        report = conflicts_with_existing(
            tag_type, config, name, firing_trigger_ids,
            account_id, container_id, workspace_id, exclude_tag_id,
        )
    except Exception:  # pragma: no cover - a lookup failure must not block
        logger.warning("Could not check the workspace for duplicates", exc_info=True)
        return [
            {
                "severity": "warning",
                "message": (
                    "The duplicate check could not run, so this tag was NOT "
                    "compared with what already exists."
                ),
                "fix": (
                    "Run find_duplicate_tags() afterwards and tell the user the "
                    "check was skipped."
                ),
            }
        ], {}

    problems: list[dict[str, str]] = []
    for conflict in report.get("blocking_conflicts", []):
        listing = "; ".join(
            f"{t['name']} (id {t['tagId']}, type {t.get('type', '?')})"
            for t in conflict["tags"]
        )
        problems.append(
            {
                "severity": "warning" if confirm_duplicate else "error",
                "message": (
                    f"[{conflict['kind']}] {conflict['headline']}: {listing}. "
                    + conflict["why"]
                ),
                "fix": (
                    "The user confirmed this duplication, so it was written "
                    "anyway. Record why in the tag notes."
                    if confirm_duplicate
                    else "NOTHING WAS WRITTEN. Show the user what already "
                    "exists, explain what you would add and why, and ask "
                    "whether to proceed. Only if they say yes, call create_tag "
                    "again with confirm_duplicate=true. Do not set that flag on "
                    "your own judgement, and do not work around this by "
                    "renaming the tag -- the comparison is by configuration, "
                    "not by name."
                ),
            }
        )

    for note in report.get("advisory", []):
        problems.append(
            {
                "severity": "info",
                "message": f"[{note['kind']}] {note['headline']}. " + note["why"],
                "fix": "Confirm the identifier is the intended one.",
            }
        )

    return problems, report


def _validate_template_tag(
    tag_type: str,
    config: dict[str, Any],
    account_id: Optional[str],
    container_id: Optional[str],
    workspace_id: Optional[str],
) -> list[dict[str, str]]:
    """Validate a community/custom template tag against the template's contract.

    The generic spec registry cannot cover these -- each template declares its
    own parameters. Reading them from `templateData` is what turns "guess the
    parameter name and get a 400" into a checkable contract.
    """
    spec = resolve_installed_template(
        tag_type, account_id, container_id, workspace_id
    )
    if spec is None:
        available = installed_template_types(account_id, container_id, workspace_id)
        listing = (
            "\n".join(f"  {t['name']}: {t['tag_type']}" for t in available)
            or "  (no templates installed in this workspace)"
        )
        return [
            {
                "severity": "error",
                "message": (
                    f"No installed template has the tag type `{tag_type}`."
                ),
                "fix": (
                    "Do not build this string yourself. A gallery template uses "
                    "`cvt_<galleryTemplateId>` (e.g. cvt_MRQN8); only a "
                    "hand-written custom template uses "
                    "`cvt_<containerId>_<templateId>`. Copy the `tag_type` "
                    "field from `list_templates` verbatim.\n"
                    f"Installed templates:\n{listing}\n"
                    "If the one you need is absent, ask the user to install it "
                    "from the Community Template Gallery."
                ),
            }
        ]

    problems: list[dict[str, str]] = []
    known = {p["name"] for p in spec.get("parameters", [])}

    # A template that declares an event and is given none is not a "base tag";
    # it is a broken event tag. Templates like Meta's and Pinterest's bootstrap
    # the pixel from ANY of their tags, so a dedicated base tag is optional --
    # and blanking the event to manufacture one produces a tag that initializes
    # the pixel and then reports nothing.
    hints = template_role_hints(spec.get("parameters", []))
    event_parameters = hints["event_parameters"]
    if event_parameters and not any(
        str(config.get(p, "")).strip() for p in event_parameters
    ):
        problems.append(
            {
                "severity": "error",
                "message": (
                    f"The {spec.get('name')} template declares an event "
                    f"parameter ({', '.join(event_parameters)}) and this tag "
                    "leaves it empty."
                ),
                "fix": (
                    "Set the event. If you wanted a base / page-view tag, this "
                    "template most likely initializes the pixel from any of its "
                    "tags already -- check `template_self_bootstraps` in "
                    "check_tagging_prerequisites. When a dedicated page-view "
                    "tag is genuinely wanted, give it the template's page-view "
                    f"event value rather than a blank one. Allowed values for "
                    f"`{event_parameters[0]}` come from get_template_spec."
                ),
            }
        )

    if not spec.get("required_parameters"):
        problems.append(
            {
                "severity": "warning",
                "message": (
                    f"The {spec.get('name')} template marks no parameter as "
                    "required, so the API will accept this tag whatever you send."
                ),
                "fix": (
                    "Confirm the account id parameter is set. A pixel tag with "
                    "no account id is created successfully and sends nothing. "
                    "Declared parameters: " + ", ".join(sorted(known))
                ),
            }
        )

    for name in spec.get("required_parameters", []):
        value = config.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            details = next(
                (p for p in spec["parameters"] if p["name"] == name), {}
            )
            problems.append(
                {
                    "severity": "error",
                    "message": (
                        f"`{name}` ({details.get('display_name') or name}) is "
                        f"required by the {spec.get('name')} template."
                    ),
                    "fix": f'Add "{name}" to parameters_json.',
                }
            )

    for param in spec.get("parameters", []):
        value = config.get(param["name"])
        if value is None:
            continue
        name = param["name"]

        allowed = param.get("allowed_values")
        if allowed:
            valid = [a["value"] for a in allowed]
            if str(value) not in valid:
                problems.append(
                    {
                        "severity": "error",
                        "message": f"`{name}` = {value!r} is not an allowed value.",
                        "fix": "Use one of: " + ", ".join(str(v) for v in valid),
                    }
                )
            continue

        # A {{Variable}} reference resolves at runtime, so no format check
        # applies -- only literals can be validated here.
        text = str(value)
        if "{{" in text:
            continue

        pattern = param.get("pattern")
        if pattern:
            try:
                matches = re.fullmatch(pattern, text) or re.match(pattern, text)
            except re.error:
                matches = True  # unparseable pattern: let the API decide
            if not matches:
                problems.append(
                    {
                        "severity": "error",
                        "message": (
                            param.get("pattern_error")
                            or f"`{name}` = {text!r} does not match the required format."
                        ),
                        "fix": (
                            f"The {spec.get('name')} template requires `{name}` to "
                            f"match the regular expression `{pattern}`. Ask the "
                            "user for the real value rather than a placeholder."
                        ),
                    }
                )

        min_len, max_len = param.get("min_length"), param.get("max_length")
        if min_len is not None and not (min_len <= len(text) <= max_len):
            problems.append(
                {
                    "severity": "error",
                    "message": (
                        param.get("length_error")
                        or f"`{name}` must be between {min_len} and {max_len} characters."
                    ),
                    "fix": f"`{name}` = {text!r} is {len(text)} characters.",
                }
            )

        if param.get("must_be_number"):
            try:
                number = float(text)
            except ValueError:
                problems.append(
                    {
                        "severity": "error",
                        "message": f"`{name}` must be a number, got {text!r}.",
                        "fix": f"Pass a numeric value or a {{{{variable}}}} for `{name}`.",
                    }
                )
            else:
                constraint = param.get("number_constraint")
                if constraint == "POSITIVE_NUMBER" and number <= 0:
                    problems.append(
                        {
                            "severity": "error",
                            "message": f"`{name}` must be positive, got {text!r}.",
                            "fix": f"Pass a value greater than zero for `{name}`.",
                        }
                    )

    unknown = [k for k in config if k not in known]
    if unknown and known:
        problems.append(
            {
                "severity": "warning",
                "message": (
                    f"The {spec.get('name')} template does not declare: "
                    + ", ".join(f"`{k}`" for k in unknown)
                    + "."
                ),
                "fix": (
                    "The API accepts unknown keys silently and they do nothing. "
                    "Declared parameters: " + ", ".join(sorted(known))
                ),
            }
        )

    return problems


def _dry_run_response(
    operation: str, parent: str, body: dict[str, Any]
) -> dict[str, Any]:
    return {
        "dry_run": True,
        "operation": operation,
        "parent": parent,
        "body_that_would_be_sent": body,
        "note": "GTM_DRY_RUN=true in .env. Nothing was written to the container.",
    }


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@tool_errors
def create_tag(
    name: str,
    tag_type: str,
    parameters_json: str = "{}",
    firing_trigger_ids: Optional[list[str]] = None,
    blocking_trigger_ids: Optional[list[str]] = None,
    notes: str = "",
    folder_id: str = "",
    paused: bool = False,
    allow_no_trigger: bool = False,
    confirm_duplicate: bool = False,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a tag in the GTM workspace.

    The payload is validated against the type's specification BEFORE it is
    sent. When it would be rejected, this returns `invalid_parameters` with the
    exact missing keys and a working example, and nothing is written. It also
    warns about unrecognised parameter keys: the GTM API accepts those silently
    and they do nothing at runtime, so a typo produces a tag that looks correct
    and never fires properly.

    **The workspace is compared with this payload before anything is written.**
    If a tag already configures the same account, already sends the same event,
    or carries the same script, NOTHING is created: the conflict comes back as
    an error naming the existing tags. Show it to the user, ask, and only if
    they agree call again with `confirm_duplicate=True`. The comparison is by
    configuration -- across Custom HTML, community templates and native Google
    tags alike -- so renaming the tag does not get past it, and nothing should.

    Before calling: run `check_tagging_prerequisites` to confirm the container
    has the foundation tag this product depends on, and `list_triggers` /
    `list_built_in_triggers` for the trigger ids. Use `get_entity_spec` when
    unsure which parameters a type needs.

    Args:
        name: tag name, already following the project naming convention
            (e.g. "GA4 - Event - purchase").
        tag_type: the API tag type. Examples: "gaawe" (GA4 Event), "googtag"
            (Google Tag), "awct" (Google Ads Conversion), "flc" (Floodlight
            Counter), "fls" (Floodlight Sales), "html" (Custom HTML).
        parameters_json: JSON string with the tag parameters, flat.
            e.g. '{"eventName": "purchase", "measurementIdOverride": "{{CONST - GA4 ID}}"}'.
            Nested objects and lists are converted to the API's `map`/`list`
            format automatically. To reference another tag by name, pass
            `{"__type__": "tagReference", "value": "Google Tag - GA4"}`; for
            `gaawe.measurementId` that conversion is applied for you.
        firing_trigger_ids: firing trigger ids. Built-in ids: "2147479553"
            (All Pages), "2147479573" (Initialization), "2147479572" (Consent
            Initialization).
        blocking_trigger_ids: blocking trigger ids.
        notes: tag notes. Record the originating requirement here.
        folder_id: destination folder id. Empty leaves the tag at the root.
        paused: create the tag paused. Useful for review before publishing.
        allow_no_trigger: permit a tag with no firing trigger. Only for a tag
            fired exclusively by another tag's sequencing. Otherwise the tag
            would never execute, and the API accepts it without complaint.
        confirm_duplicate: create the tag even though it duplicates an existing
            one. **Only ever set this after the user has seen the conflict and
            explicitly agreed to it in the conversation.** It records their
            decision; it is not a way to silence the check.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The created tag (including `tagId`), or the payload in dry-run mode.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    config = _load_json_arg(parameters_json, "parameters_json")

    if tag_type.startswith("cvt_"):
        problems = _validate_template_tag(
            tag_type, config, account_id, container_id, workspace_id
        )
    else:
        problems = validate_entity("tag", tag_type, config)

    # A `{{Name}}` pointing at nothing resolves to an empty string at runtime,
    # silently; a tag with no trigger never runs. Both are accepted by the API.
    problems += _reference_problems(config, account_id, container_id, workspace_id)
    problems += _trigger_problems(tag_type, firing_trigger_ids, allow_no_trigger)
    duplicate_problems, duplicate_report = _duplicate_gate(
        tag_type, config, name, firing_trigger_ids, confirm_duplicate,
        account_id, container_id, workspace_id,
    )
    problems += duplicate_problems

    if any(p["severity"] == "error" for p in problems):
        refusal = format_problems("tag", tag_type, problems)
        if duplicate_report.get("blocking_conflicts"):
            refusal["created"] = False
            refusal["duplicate_conflicts"] = duplicate_report["blocking_conflicts"]
            refusal["next_step"] = duplicate_report["next_step"]
        return refusal

    body: dict[str, Any] = {"name": name, "type": tag_type}
    if config:
        body["parameter"] = to_gtm_parameters(config, tag_type)
    if firing_trigger_ids:
        body["firingTriggerId"] = [str(t) for t in firing_trigger_ids]
    if blocking_trigger_ids:
        body["blockingTriggerId"] = [str(t) for t in blocking_trigger_ids]
    if notes:
        body["notes"] = notes
    if folder_id:
        body["parentFolderId"] = str(folder_id)
    if paused:
        body["paused"] = True

    if settings.dry_run:
        response = _dry_run_response("create_tag", parent, body)
        response["warnings"] = problems
        return response

    created = workspaces().tags().create(parent=parent, body=body).execute()
    result = {
        "created": True,
        "tagId": created.get("tagId"),
        "name": created.get("name"),
        "type": created.get("type"),
        "path": created.get("path"),
        "tagManagerUrl": created.get("tagManagerUrl"),
    }
    if problems:
        result["warnings"] = problems
    return result


@tool_errors
def update_tag(
    tag_id: str,
    name: str = "",
    parameters_json: str = "",
    firing_trigger_ids: Optional[list[str]] = None,
    notes: str = "",
    confirm_duplicate: bool = False,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Update an existing tag, preserving the fields you do not pass.

    A GTM update replaces the whole entity, so this tool reads the current tag,
    applies only the requested changes and sends the full body back, using the
    `fingerprint` so it never silently overwrites someone else's edit in the
    same workspace.

    **Changing parameters runs the same duplication check as `create_tag`.**
    Pointing an existing tag at an account, destination or event that another
    tag already covers produces exactly the duplication creating a new tag
    would, by a quieter route. When that happens NOTHING is written: relay the
    conflict, ask, and only then call again with `confirm_duplicate=True`. The
    tag being edited is excluded from the comparison, so a no-op edit is never
    reported as a conflict with itself.

    Args:
        tag_id: numeric tag id.
        name: new name. Empty keeps the current one.
        parameters_json: JSON string with parameters to overwrite or add. Empty
            keeps the current parameters. The values you pass are merged on top
            of what already exists.
        firing_trigger_ids: new firing trigger list. None keeps the current one.
        notes: new notes. Empty keeps the current ones.
        confirm_duplicate: apply the change even though it duplicates an
            existing tag. **Only after the user has seen the conflict and
            agreed.** It records their decision; it is not a way to silence the
            check.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The updated tag, or the payload in dry-run mode.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    path = f"{parent}/tags/{tag_id}"
    current = workspaces().tags().get(path=path).execute()

    body = dict(current)
    if name:
        body["name"] = name
    if notes:
        body["notes"] = notes
    if firing_trigger_ids is not None:
        body["firingTriggerId"] = [str(t) for t in firing_trigger_ids]
    if parameters_json.strip():
        merged = parameters_to_dict(current.get("parameter"))
        merged.update(_load_json_arg(parameters_json, "parameters_json"))
        tag_type = current.get("type", "")
        problems = validate_entity("tag", tag_type, merged)
        problems += _reference_problems(
            merged, account_id, container_id, workspace_id
        )
        duplicate_problems, duplicate_report = _duplicate_gate(
            tag_type,
            merged,
            name or current.get("name", ""),
            body.get("firingTriggerId"),
            confirm_duplicate,
            account_id,
            container_id,
            workspace_id,
            exclude_tag_id=str(tag_id),
        )
        problems += duplicate_problems
        if any(p["severity"] == "error" for p in problems):
            refusal = format_problems("tag", tag_type, problems)
            if duplicate_report.get("blocking_conflicts"):
                refusal["updated"] = False
                refusal["duplicate_conflicts"] = duplicate_report["blocking_conflicts"]
                refusal["next_step"] = duplicate_report["next_step"]
            return refusal
        body["parameter"] = to_gtm_parameters(merged, tag_type)

    if settings.dry_run:
        return _dry_run_response("update_tag", path, body)

    updated = (
        workspaces()
        .tags()
        .update(path=path, fingerprint=current.get("fingerprint"), body=body)
        .execute()
    )
    return {
        "updated": True,
        "tagId": updated.get("tagId"),
        "name": updated.get("name"),
        "path": updated.get("path"),
    }


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


@tool_errors
def create_trigger(
    name: str,
    trigger_type: str,
    custom_event_name: str = "",
    filters_json: str = "[]",
    parameters_json: str = "{}",
    notes: str = "",
    folder_id: str = "",
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a trigger in the GTM workspace.

    Always run `list_triggers` first: reusing an existing trigger beats
    creating a duplicate. For All Pages / Initialization, do not create
    anything -- use the reserved ids from `list_built_in_triggers`.

    Args:
        name: trigger name (e.g. "CE - purchase").
        trigger_type: the API type. Examples: "customEvent", "pageview",
            "domReady", "windowLoaded", "click", "linkClick", "formSubmission",
            "elementVisibility", "scrollDepth", "timer", "historyChange",
            "youTubeVideo", "init", "consentInit".
        custom_event_name: required when trigger_type is "customEvent". The
            dataLayer event name (e.g. "purchase").
        filters_json: JSON string with extra conditions, shaped as
            [{"variable": "Page Path", "operator": "contains",
            "value": "/checkout"}]. Valid operators: equals, contains,
            startsWith, endsWith, matchRegex, matchCssSelector, urlMatches,
            greater, greaterOrEquals, less, lessOrEquals.
        parameters_json: JSON string with extra trigger parameters
            (e.g. '{"verticalThresholdsPercent": "25,50,75,100"}').
        notes: trigger notes.
        folder_id: destination folder id. Empty leaves it at the root.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The created trigger (including `triggerId`), or the dry-run payload.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)

    if trigger_type not in TRIGGER_TYPES:
        raise ValueError(
            f"Unknown trigger_type '{trigger_type}'. Valid types: "
            + ", ".join(sorted(TRIGGER_TYPES))
            + ". Note that All Pages, Initialization and Consent "
            "Initialization are reserved built-in triggers -- do not recreate "
            "them, use the ids from `list_built_in_triggers`."
        )

    body: dict[str, Any] = {"name": name, "type": trigger_type}

    if trigger_type == "customEvent":
        if not custom_event_name:
            raise ValueError(
                "custom_event_name is required when trigger_type is "
                "'customEvent'. The API rejects a custom-event trigger without "
                "exactly one custom-event filter."
            )
        body["customEventFilter"] = [
            {
                "type": "equals",
                "parameter": [
                    {"type": "template", "key": "arg0", "value": "{{_event}}"},
                    {"type": "template", "key": "arg1", "value": custom_event_name},
                ],
            }
        ]

    raw_filters = filters_json.strip() or "[]"
    try:
        filters = json.loads(raw_filters)
    except json.JSONDecodeError as exc:
        raise ValueError(f"`filters_json` is not valid JSON: {exc}") from exc
    if not isinstance(filters, list):
        raise ValueError("`filters_json` must be a list of conditions.")

    if filters:
        body["filter"] = [
            {
                "type": condition.get("operator", "equals"),
                "parameter": [
                    {
                        "type": "template",
                        "key": "arg0",
                        "value": "{{%s}}" % condition["variable"]
                        if not str(condition["variable"]).startswith("{{")
                        else condition["variable"],
                    },
                    {
                        "type": "template",
                        "key": "arg1",
                        "value": str(condition.get("value", "")),
                    },
                ],
            }
            for condition in filters
        ]

    config = _load_json_arg(parameters_json, "parameters_json")

    reference_problems = _reference_problems(
        {"filters": filters, "parameters": config},
        account_id,
        container_id,
        workspace_id,
    )
    if any(p["severity"] == "error" for p in reference_problems):
        return format_problems("trigger", trigger_type, reference_problems)

    if config:
        body["parameter"] = to_gtm_parameters(config)
    if notes:
        body["notes"] = notes
    if folder_id:
        body["parentFolderId"] = str(folder_id)

    if settings.dry_run:
        return _dry_run_response("create_trigger", parent, body)

    created = workspaces().triggers().create(parent=parent, body=body).execute()
    return {
        "created": True,
        "triggerId": created.get("triggerId"),
        "name": created.get("name"),
        "type": created.get("type"),
        "path": created.get("path"),
    }


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------


@tool_errors
def create_variable(
    name: str,
    variable_type: str,
    parameters_json: str = "{}",
    notes: str = "",
    folder_id: str = "",
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a user-defined variable in the GTM workspace.

    Args:
        name: variable name (e.g. "DLV - ecommerce.transaction_id").
        variable_type: the API type. Examples: "v" (Data Layer Variable), "c"
            (Constant), "jsm" (Custom JavaScript), "j" (JavaScript Variable),
            "u" (URL), "k" (1st Party Cookie), "d" (DOM Element), "smm"
            (Lookup Table), "remm" (RegEx Table), "aev" (Auto-Event Variable).
        parameters_json: JSON string with the parameters. Examples:
            Data Layer Variable -> '{"name": "ecommerce.transaction_id",
            "dataLayerVersion": 2}'; Constant -> '{"value": "G-XXXXXXX"}'.
        notes: variable notes.
        folder_id: destination folder id. Empty leaves it at the root.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The created variable (including `variableId`), or the dry-run payload.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    config = _load_json_arg(parameters_json, "parameters_json")

    problems = validate_entity("variable", variable_type, config)
    problems += _reference_problems(config, account_id, container_id, workspace_id)
    if any(p["severity"] == "error" for p in problems):
        return format_problems("variable", variable_type, problems)

    body: dict[str, Any] = {"name": name, "type": variable_type}
    if config:
        body["parameter"] = to_gtm_parameters(config, variable_type)
    if notes:
        body["notes"] = notes
    if folder_id:
        body["parentFolderId"] = str(folder_id)

    if settings.dry_run:
        response = _dry_run_response("create_variable", parent, body)
        response["warnings"] = problems
        return response

    created = workspaces().variables().create(parent=parent, body=body).execute()
    result = {
        "created": True,
        "variableId": created.get("variableId"),
        "name": created.get("name"),
        "type": created.get("type"),
        "path": created.get("path"),
    }
    if problems:
        result["warnings"] = problems
    return result


# ---------------------------------------------------------------------------
# Renaming (naming-convention cleanup)
# ---------------------------------------------------------------------------


@tool_errors
def rename_entity(
    entity_type: str,
    entity_id: str,
    new_name: str,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Rename a tag, trigger, variable or folder, preserving its configuration.

    Use it to apply the project naming convention without recreating entities.
    WARNING: renaming a variable does NOT update the `{{Old name}}` references
    scattered across the container -- check the usages first.

    Args:
        entity_type: "tag", "trigger", "variable" or "folder".
        entity_id: numeric entity id.
        new_name: the new name, already following the convention.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        Confirmation with the old and new name, or the dry-run payload.
    """
    if entity_type not in _ENTITY_RESOURCES:
        raise ValueError(
            f"Invalid entity_type: '{entity_type}'. Use one of: "
            + ", ".join(_ENTITY_RESOURCES)
        )

    resource_name, _ = _ENTITY_RESOURCES[entity_type]
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    path = f"{parent}/{resource_name}/{entity_id}"
    resource = getattr(workspaces(), resource_name)()

    current = resource.get(path=path).execute()
    old_name = current.get("name")
    body = dict(current)
    body["name"] = new_name

    if settings.dry_run:
        return _dry_run_response("rename_entity", path, body)

    resource.update(
        path=path, fingerprint=current.get("fingerprint"), body=body
    ).execute()
    return {
        "renamed": True,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_name": old_name,
        "new_name": new_name,
    }
