"""The `check_id_consistency` audit tool.

Kept separate from `gtm_read` because the interesting logic is the comparison,
not the fetching, and that logic is worth testing without an API.
"""

from __future__ import annotations

from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import paginate
from .gtm_client import parameters_to_dict
from .gtm_client import setting_values
from .gtm_client import tool_errors
from .gtm_client import workspaces
from .references import extract_references
from .gtm_templates import index_templates
from .identifiers import classify_destination
from .identifiers import constant_values
from .identifiers import find_name_collisions
from .identifiers import find_near_miss_references
from .identifiers import looks_like_destination
from .identifiers import resolve_value
from .media_platforms import MEDIA_PLATFORMS

#: Where each tag type declares the destination it sends to.
_DESTINATION_PARAMETERS = {
    "googtag": ("tagId",),
    "gaawc": ("measurementId",),
    "gaawe": ("measurementIdOverride",),
    "awct": ("conversionId",),
    "sp": ("conversionId",),
    "flc": ("advertiserId",),
    "fls": ("advertiserId",),
}

#: Tag types that CONFIGURE a destination, versus those that merely use one.
_BASE_TAG_TYPES = {"googtag", "gaawc"}


def _google_ads_forms(value: str) -> set[str]:
    """`awct` stores the digits only; `googtag` stores the full `AW-` id."""
    bare = value.upper().removeprefix("AW-")
    return {value.upper(), bare, f"AW-{bare}"}


def audit_google_destinations(
    tags: list[dict[str, Any]], constants: dict[str, str]
) -> list[dict[str, Any]]:
    """Compare the destinations event tags use against the ones base tags configure."""
    configured: dict[str, list[dict[str, Any]]] = {}
    consumers: list[dict[str, Any]] = []

    for tag in tags:
        tag_type = tag.get("type", "")
        parameters = _DESTINATION_PARAMETERS.get(tag_type)
        if not parameters:
            continue
        flat = parameters_to_dict(tag.get("parameter"))

        for parameter in parameters:
            raw = flat.get(parameter)
            value, kind = resolve_value(raw, constants)
            entry = {
                "tagId": tag.get("tagId"),
                "name": tag.get("name"),
                "type": tag_type,
                "parameter": parameter,
                "raw": str(raw) if raw is not None else None,
                "value": value,
                "resolution": kind,
                "paused": tag.get("paused", False),
            }
            if tag_type in _BASE_TAG_TYPES:
                if value:
                    configured.setdefault(value.upper(), []).append(entry)
            else:
                consumers.append(entry)

    findings: list[dict[str, Any]] = []
    configured_upper = set(configured)
    ads_configured = {
        form
        for destination in configured_upper
        if destination.startswith("AW-")
        for form in _google_ads_forms(destination)
    }

    for consumer in consumers:
        value, kind = consumer["value"], consumer["resolution"]

        if kind == "unresolved":
            findings.append(
                {
                    "severity": "medium",
                    "kind": "destination_not_statically_checkable",
                    "tag": consumer,
                    "message": (
                        f"`{consumer['name']}` sets {consumer['parameter']} from "
                        f"{consumer['raw']}, which is not a constant, so its "
                        "destination cannot be verified from the container."
                    ),
                    "fix": (
                        "Use a constant variable for a fixed destination id. A "
                        "data layer or JavaScript variable here means nobody "
                        "can tell which property receives the data without "
                        "loading the site."
                    ),
                }
            )
            continue

        if kind == "missing" or not value:
            continue  # absence is the reference/spec check's job, not this one

        if consumer["type"] in ("awct", "sp"):
            matched = bool(ads_configured & _google_ads_forms(value))
        else:
            matched = value.upper() in configured_upper

        if matched:
            continue

        product = classify_destination(value) or "an unknown product"
        known = sorted(configured_upper) or ["(no base tag configures any destination)"]
        findings.append(
            {
                "severity": "critical",
                "kind": "destination_without_base_tag",
                "tag": consumer,
                "message": (
                    f"`{consumer['name']}` sends to {value} ({product}), but no "
                    "base tag in this container configures that destination."
                ),
                "fix": (
                    f"Either correct the id to one that is configured "
                    f"({', '.join(known)}), or create a base tag for {value}. "
                    "A Google Tag exists per destination: one configured for a "
                    "GA4 property does nothing for a different property, and "
                    "nothing for Google Ads."
                ),
            }
        )

        if not looks_like_destination(value):
            findings[-1]["message"] += (
                f" The value {value!r} does not even have the shape of a "
                "destination id."
            )

    return findings


def audit_media_ids(
    tags: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    constants: dict[str, str],
) -> list[dict[str, Any]]:
    """Report a platform whose tags disagree about the account id.

    Google is not special here: a Meta event tag pointing at one pixel while
    the rest of the container points at another sends conversions to the wrong
    ad account, and nothing warns about it.
    """
    platform_by_type, hints_by_type = index_templates(templates)

    by_platform: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for tag in tags:
        tag_type = tag.get("type", "")
        platform = platform_by_type.get(tag_type)
        if not platform:
            continue
        hints = hints_by_type.get(tag_type, {})
        flat = parameters_to_dict(tag.get("parameter"))
        readable = {**setting_values(flat), **flat}

        id_parameter = next(
            (p for p in hints.get("id_parameters", []) if p in readable), None
        )
        if not id_parameter:
            continue
        value, kind = resolve_value(readable.get(id_parameter), constants)
        if kind in ("missing", "unresolved") or not value:
            continue
        by_platform.setdefault(platform, {}).setdefault(value, []).append(
            {
                "tagId": tag.get("tagId"),
                "name": tag.get("name"),
                "parameter": id_parameter,
                "value": value,
            }
        )

    findings = []
    for platform, by_value in by_platform.items():
        if len(by_value) < 2:
            continue
        label = MEDIA_PLATFORMS[platform].label
        detail = "; ".join(
            f"{value} ({', '.join(t['name'] for t in tags_)})"
            for value, tags_ in sorted(by_value.items())
        )
        findings.append(
            {
                "severity": "critical",
                "kind": "media_account_id_mismatch",
                "platform": platform,
                "message": (
                    f"{label} tags use {len(by_value)} different account ids: {detail}."
                ),
                "fix": (
                    "Confirm which account is correct and align every tag on it, "
                    "or confirm with the user that the site genuinely reports to "
                    "more than one ad account. Put the id in a constant variable "
                    "so it cannot drift again."
                ),
                "ids": {value: tags_ for value, tags_ in by_value.items()},
            }
        )
    return findings


@tool_errors
def check_id_consistency(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Verify that every destination id a tag sends to is actually configured.

    A tag can carry a valid-looking measurement or pixel id that no base tag
    ever configures. GTM accepts it, the tag fires, and the data goes to a
    property nobody watches. Nothing in the UI compares the two.

    Checks four things, resolving constant variables so comparison sees through
    `{{CONST - ...}}` references:

    1. Every GA4 / Google Ads / Floodlight destination used by an event or
       conversion tag is configured by a base tag in this container.
    2. Third-party platforms do not disagree with themselves about the account
       id -- a Meta tag on one pixel while the rest use another.
    3. Variable names that differ only in case or punctuation
       (`CONST - GA4 Measurement ID` vs `... id`). GTM treats them as separate
       variables, so fixing one silently leaves the other empty.
    4. Destination ids supplied by a non-constant variable, which cannot be
       verified from the container at all.

    Run it in every audit. It is the check that turns "the tags exist" into
    "the tags send where you think they send".

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        `clean`, `findings` (each with severity, message and fix),
        `configured_destinations` and `variable_name_collisions`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    ws = workspaces()

    tags = paginate(ws.tags(), "list", "tag", parent=parent)
    templates = paginate(ws.templates(), "list", "template", parent=parent)
    raw_variables = paginate(ws.variables(), "list", "variable", parent=parent)

    variables = [
        {
            "name": v.get("name"),
            "type": v.get("type"),
            "parameters": parameters_to_dict(v.get("parameter")),
        }
        for v in raw_variables
    ]
    constants = constant_values(variables)

    findings = audit_google_destinations(tags, constants)
    findings += audit_media_ids(tags, templates, constants)

    # A reference one letter away from a real variable is the single most
    # misleading state a container can be in: the variable exists, the tag
    # looks wired up, and the value sent is empty.
    variable_names = [v["name"] for v in variables if v["name"]]
    known = set(variable_names)
    unresolved = sorted(
        {
            reference
            for tag in tags
            for reference in extract_references(parameters_to_dict(tag.get("parameter")))
            if reference not in known
        }
    )
    for near_miss in find_near_miss_references(unresolved, variable_names):
        users = [
            t.get("name")
            for t in tags
            if near_miss["reference"]
            in extract_references(parameters_to_dict(t.get("parameter")))
        ]
        findings.append(
            {
                "severity": "critical",
                "kind": "reference_near_miss",
                "message": (
                    f"`{{{{{near_miss['reference']}}}}}` does not exist, but "
                    + " and ".join(f"`{n}`" for n in near_miss["existing"])
                    + f" does. {near_miss['why']} Affected: "
                    + ", ".join(users)
                ),
                "fix": (
                    "Do NOT create a second variable. Repoint these tags at "
                    f"`{near_miss['existing'][0]}` with update_tag, or rename "
                    "one so a single spelling remains."
                ),
                "reference": near_miss["reference"],
                "existing": near_miss["existing"],
                "used_by": users,
            }
        )

    collisions = find_name_collisions(variable_names)
    for collision in collisions:
        findings.append(
            {
                "severity": "high",
                "kind": "variable_name_collision",
                "message": (
                    "Variable names differing only in case or punctuation: "
                    + ", ".join(f"`{v}`" for v in collision["variants"])
                    + ". " + collision["why"]
                ),
                "fix": (
                    "Decide which name is canonical, repoint every tag to it, "
                    "and remove the other. Fixing only one of them leaves the "
                    "tags on the other still sending an empty value."
                ),
                "variants": collision["variants"],
            }
        )

    configured = sorted(
        {
            str(parameters_to_dict(t.get("parameter")).get(p) or "")
            for t in tags
            if t.get("type") in _BASE_TAG_TYPES
            for p in _DESTINATION_PARAMETERS.get(t.get("type", ""), ())
        }
        - {""}
    )

    by_severity: dict[str, int] = {}
    for finding in findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1

    return {
        "parent": parent,
        "clean": not findings,
        "finding_count": len(findings),
        "by_severity": by_severity,
        "findings": findings,
        "configured_destinations": configured,
        "known_constants": constants,
        "variable_name_collisions": collisions,
        "unresolved_references": unresolved,
        "note": (
            "A destination id that no base tag configures is a critical "
            "finding: the tag fires and the data goes nowhere useful. Constant "
            "variables are resolved before comparing, so `{{CONST - ...}}` is "
            "checked by value, not by name."
        ),
    }
