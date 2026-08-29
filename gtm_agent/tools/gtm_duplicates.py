"""Finding pixels initialised more than once, however they were built."""

from __future__ import annotations

from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import paginate
from .gtm_client import parameters_to_dict
from .gtm_client import tool_errors
from .gtm_client import workspaces
from .gtm_prerequisites import classify_media_role_for_tag
from .gtm_templates import index_templates
from .identifiers import constant_values
from .identifiers import variable_value_candidates
from .tag_identity import PRODUCT_LABELS
from .tag_identity import conversion_config_of
from .tag_identity import describe_base_overlap
from .tag_identity import event_only_platforms
from .tag_identity import html_fingerprint
from .tag_identity import initialisations_of
from .vendor_snippets import platform_label


def build_identity_context(
    tags: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    variables: list[dict[str, Any]],
) -> dict[str, Any]:
    """Everything the identity functions need to read a container consistently."""
    platform_by_type, template_hints = index_templates(templates)

    normalized = [
        {
            "name": v.get("name"),
            "type": v.get("type"),
            "parameters": parameters_to_dict(v.get("parameter")),
        }
        for v in variables
    ]

    # Only a template tag in the SETUP role initialises its pixel. Reusing the
    # media role classifier keeps that judgement in one place; two
    # implementations of "is this a base tag" would drift apart.
    template_roles = {
        str(tag.get("tagId")): classify_media_role_for_tag(
            tag, platform_by_type, template_hints
        )
        for tag in tags
        if tag.get("type", "") in platform_by_type
    }

    return {
        "platform_by_type": platform_by_type,
        "template_hints": template_hints,
        "constants": constant_values(normalized),
        # What each variable COULD resolve to, not only what it IS. A lookup
        # table routing 27 URL patterns to 27 measurement ids is one tag that
        # already covers 27 properties.
        "variable_candidates": variable_value_candidates(normalized),
        "template_roles": template_roles,
    }


def _fetch(
    account_id: Optional[str], container_id: Optional[str], workspace_id: Optional[str]
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    ws = workspaces()
    tags = paginate(ws.tags(), "list", "tag", parent=parent)
    templates = paginate(ws.templates(), "list", "template", parent=parent)
    variables = paginate(ws.variables(), "list", "variable", parent=parent)
    return parent, tags, build_identity_context(tags, templates, variables)


def _entry(tag: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "tagId": tag.get("tagId"),
        "name": tag.get("name"),
        "type": tag.get("type"),
        "paused": tag.get("paused", False),
        "firingTriggerId": [str(t) for t in tag.get("firingTriggerId") or []],
        **extra,
    }


def collect_findings(
    tags: list[dict[str, Any]], context: dict[str, Any]
) -> dict[str, Any]:
    """The whole analysis, free of API calls so the rules can be tested directly."""
    constants = context.get("constants", {})

    # --- 1. Accounts initialised more than once ---------------------------
    by_account: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for tag in tags:
        for init in initialisations_of(tag, **context):
            by_account.setdefault(init.key, []).append(
                _entry(
                    tag,
                    implementation=init.implementation,
                    account=init.account,
                    product=init.product,
                    label=init.label,
                )
            )

    base_groups = []
    for entries in by_account.values():
        if len(entries) < 2:
            continue
        verdict = describe_base_overlap(entries)
        if not verdict["severity"]:
            continue
        base_groups.append(
            {
                "kind": "base",
                "severity": verdict["severity"],
                "identity": entries[0]["label"],
                "product": entries[0]["product"],
                "account": entries[0]["account"],
                "why": verdict["reason"],
                "tags": [
                    {
                        k: v
                        for k, v in entry.items()
                        if k not in ("product", "label", "account")
                    }
                    for entry in entries
                ],
            }
        )

    # --- 2. Conversion tags with an identical configuration ---------------
    by_conversion: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for tag in tags:
        config = conversion_config_of(tag, constants)
        if config:
            by_conversion.setdefault(config, []).append(_entry(tag))

    conversion_groups = []
    for (product, values), entries in by_conversion.items():
        active = [e for e in entries if not e["paused"]]
        if len(active) < 2:
            continue
        trigger_sets = [frozenset(e["firingTriggerId"]) for e in active]
        shared = any(
            a & b for i, a in enumerate(trigger_sets) for b in trigger_sets[i + 1 :]
        )
        conversion_groups.append(
            {
                "kind": "conversion",
                "severity": "critical" if shared else "medium",
                "identity": f"{PRODUCT_LABELS.get(product, product)} / "
                + " / ".join(v for v in values if v),
                "product": product,
                "why": (
                    "Identical conversion configuration on the same trigger: "
                    "the conversion is counted twice."
                    if shared
                    else "Identical conversion configuration on different "
                    "triggers. Legitimate when one conversion is measured on "
                    "several events -- confirm it is deliberate rather than a "
                    "forgotten copy."
                ),
                "tags": entries,
            }
        )

    # --- 3. Identical scripts, vendor unknown -----------------------------
    already_grouped = {
        entry["tagId"]
        for group in base_groups
        for entry in group["tags"]
        if entry.get("implementation") == "html"
    }
    by_script: dict[str, list[dict[str, Any]]] = {}
    for tag in tags:
        fingerprint = html_fingerprint(tag)
        if fingerprint and tag.get("tagId") not in already_grouped:
            by_script.setdefault(fingerprint, []).append(_entry(tag))

    script_groups = [
        {
            "kind": "script",
            "severity": "high",
            "identity": f"Identical script ({fingerprint})",
            "why": (
                "These Custom HTML tags carry the same script, ignoring "
                "whitespace and variable references. The vendor is not in the "
                "registry so the account cannot be read, but two copies of one "
                "snippet still run twice."
            ),
            "tags": entries,
        }
        for fingerprint, entries in by_script.items()
        if len([e for e in entries if not e["paused"]]) > 1
    ]

    # --- 4. Event calls that initialise nothing ---------------------------
    dependents = [
        _entry(tag, platform=platform_label(platform))
        for tag in tags
        for platform in event_only_platforms(tag)
    ]

    groups = base_groups + conversion_groups + script_groups
    order = {"critical": 0, "high": 1, "medium": 2}
    groups.sort(key=lambda g: (order.get(g["severity"], 3), g["identity"]))

    by_severity: dict[str, int] = {}
    for group in groups:
        by_severity[group["severity"]] = by_severity.get(group["severity"], 0) + 1

    return {
        "clean": not groups,
        "group_count": len(groups),
        "by_severity": by_severity,
        "groups": groups,
        "accounts_initialised": sorted(
            {entries[0]["label"] for entries in by_account.values()}
        ),
        "event_tags_depending_on_a_base_tag": dependents,
    }


@tool_errors
def find_duplicate_tags(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Find pixels initialised more than once, whatever the implementation.

    Duplication is a question about BASE tags. Most platforms carry the account
    id only in the initialisation call -- `fbq('init', '123')` -- and their
    event tags use whichever library that call loaded. So this compares
    initialisations, not every tag: twenty GA4 tags firing `click` on twenty
    pages are twenty legitimate tags, and grouping them would be noise.

    Four things are reported:

    * `base` -- the same account initialised twice, by native Google tag,
      community template, hand-written script or image pixel. **critical** when
      the initialisations share a trigger or mix implementations (a leftover
      from a migration); **high** otherwise, since mutually exclusive triggers
      are possible but rare.
    * `conversion` -- two conversion tags with an identical configuration.
      Unlike a GA4 event, a Google Ads conversion carries its own id and label,
      so a second one on the same trigger double-counts. On different triggers
      it is usually deliberate: **medium**, a question rather than a fault.
    * `script` -- two Custom HTML tags with the same script, ignoring
      whitespace and `{{Variable}}` references. This catches a vendor that no
      registry names.
    * `event_tags_depending_on_a_base_tag` -- event calls that initialise
      nothing. Not duplicates, but they break outright if their base tag goes.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        `clean`, `groups`, `by_severity`, `accounts_initialised` and the
        dependent event tags.
    """
    parent, tags, context = _fetch(account_id, container_id, workspace_id)
    result = collect_findings(tags, context)
    result["parent"] = parent
    result["note"] = (
        "Only initialisations are compared. An event tag carries no account on "
        "most platforms, so it cannot duplicate a base tag and is listed "
        "separately instead of grouped."
    )
    return result
