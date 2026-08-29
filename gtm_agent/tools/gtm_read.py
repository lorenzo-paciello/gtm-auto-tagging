"""READ tools for the GTM container: what is in it, and what is broken in it.

Whether the container has the *foundation* a given tag depends on is a
different question with a much larger body of rules behind it, and it lives in
`gtm_prerequisites`.
"""

from __future__ import annotations

from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import get_gtm_service
from .references import check_references
from .gtm_client import paginate
from .gtm_client import parameters_to_dict
from .gtm_client import summarize_folder
from .gtm_client import summarize_tag
from .gtm_client import summarize_trigger
from .gtm_client import summarize_variable
from .gtm_client import tool_errors
from .gtm_client import workspaces


@tool_errors
def list_accounts() -> dict[str, Any]:
    """List the GTM accounts reachable with the configured credentials.

    Use this when the user does not know which account_id to work with.

    Returns:
        A dict with an `accounts` key (accountId, name, path).
    """
    accounts = paginate(get_gtm_service().accounts(), "list", "account")
    return {
        "count": len(accounts),
        "accounts": [
            {
                "accountId": item.get("accountId"),
                "name": item.get("name"),
                "path": item.get("path"),
            }
            for item in accounts
        ],
    }


@tool_errors
def list_containers(account_id: Optional[str] = None) -> dict[str, Any]:
    """List the containers inside a GTM account.

    Args:
        account_id: account id. Falls back to GTM_ACCOUNT_ID from .env.

    Returns:
        A dict with a `containers` key (containerId, name, publicId,
        usageContext = web/amp/server/ios/android).
    """
    account = (account_id or "").strip() or settings.account_id
    if not account:
        raise ValueError("account_id not provided and GTM_ACCOUNT_ID is unset in .env.")
    containers = paginate(
        get_gtm_service().accounts().containers(),
        "list",
        "container",
        parent=f"accounts/{account}",
    )
    return {
        "accountId": account,
        "count": len(containers),
        "containers": [
            {
                "containerId": item.get("containerId"),
                "name": item.get("name"),
                "publicId": item.get("publicId"),
                "usageContext": item.get("usageContext", []),
                "taggingServerUrls": item.get("taggingServerUrls"),
            }
            for item in containers
        ],
    }


@tool_errors
def list_workspaces(
    account_id: Optional[str] = None, container_id: Optional[str] = None
) -> dict[str, Any]:
    """List the workspaces (drafts) of a container.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.

    Returns:
        A dict with a `workspaces` key (workspaceId, name, description).
    """
    account = (account_id or "").strip() or settings.account_id
    container = (container_id or "").strip() or settings.container_id
    if not account or not container:
        raise ValueError("account_id/container_id not provided and missing from .env.")
    items = paginate(
        workspaces(),
        "list",
        "workspace",
        parent=f"accounts/{account}/containers/{container}",
    )
    return {
        "count": len(items),
        "workspaces": [
            {
                "workspaceId": item.get("workspaceId"),
                "name": item.get("name"),
                "description": item.get("description"),
            }
            for item in items
        ],
    }


@tool_errors
def list_tags(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    detailed: bool = False,
) -> dict[str, Any]:
    """List every tag in a GTM workspace.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.
        detailed: when True, also return each tag's configuration parameters.
            Keep it False (default) for broad inventories and audits, since the
            full payload burns a lot of tokens.

    Returns:
        A dict with `count` and `tags`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    tags = paginate(workspaces().tags(), "list", "tag", parent=parent)

    def render(tag: dict[str, Any]) -> dict[str, Any]:
        summary = summarize_tag(tag)
        if detailed:
            summary["parameters"] = parameters_to_dict(tag.get("parameter"))
        return summary

    return {"parent": parent, "count": len(tags), "tags": [render(t) for t in tags]}


@tool_errors
def get_tag(
    tag_id: str,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Return the FULL configuration of one tag.

    Use it when you need to inspect parameters, consent settings or the raw
    body of a tag before replicating or fixing the configuration.

    Args:
        tag_id: numeric tag id (the `tagId` field).
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The tag as returned by the API, plus `parameters_flat` (parameters
        already flattened into a dictionary) for easier reading.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    tag = workspaces().tags().get(path=f"{parent}/tags/{tag_id}").execute()
    tag["parameters_flat"] = parameters_to_dict(tag.get("parameter"))
    return tag


@tool_errors
def list_triggers(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """List every trigger in a workspace.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `count` and `triggers`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    triggers = paginate(workspaces().triggers(), "list", "trigger", parent=parent)
    return {
        "parent": parent,
        "count": len(triggers),
        "triggers": [summarize_trigger(t) for t in triggers],
    }


@tool_errors
def list_variables(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """List the user-defined variables in a workspace.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `count` and `variables`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    variables = paginate(workspaces().variables(), "list", "variable", parent=parent)
    return {
        "parent": parent,
        "count": len(variables),
        "variables": [summarize_variable(v) for v in variables],
    }


@tool_errors
def list_built_in_variables(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """List the built-in variables enabled in the workspace.

    Important for audits: variables such as Click Element, Form ID or Page Path
    must be enabled for the matching triggers and tags to work at all.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `count` and `built_in_variables` (name, type).
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    items = paginate(
        workspaces().built_in_variables(), "list", "builtInVariable", parent=parent
    )
    return {
        "parent": parent,
        "count": len(items),
        "built_in_variables": [
            {"name": item.get("name"), "type": item.get("type")} for item in items
        ],
    }


@tool_errors
def list_folders(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """List the folders that exist in the workspace.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `count` and `folders` (folderId, name, notes).
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    folders = paginate(workspaces().folders(), "list", "folder", parent=parent)
    return {
        "parent": parent,
        "count": len(folders),
        "folders": [summarize_folder(f) for f in folders],
    }


@tool_errors
def find_broken_references(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Find `{{Variable}}` references that resolve to nothing, and tags that never fire.

    Two failures GTM never reports. A reference to a variable that does not
    exist resolves to an EMPTY STRING at runtime -- the tag fires, the UI looks
    correct, and the value it sends is blank. A tag with no firing trigger
    simply never runs. The API accepts both without comment, so only this kind
    of sweep finds them.

    Run it as part of every audit, and after any batch of tag creation.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        `broken_references` (each missing name, why, and which entities use
        it), `tags_without_trigger`, and `clean` when both are empty.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    ws = workspaces()

    tags = paginate(ws.tags(), "list", "tag", parent=parent)
    triggers = paginate(ws.triggers(), "list", "trigger", parent=parent)
    variables = paginate(ws.variables(), "list", "variable", parent=parent)
    built_ins = paginate(
        ws.built_in_variables(), "list", "builtInVariable", parent=parent
    )

    variable_names = [v.get("name") for v in variables if v.get("name")]
    built_in_names = [b.get("name") for b in built_ins if b.get("name")]

    # Group by the missing name: ten tags sharing one broken reference is one
    # problem with one fix, not ten findings.
    by_reference: dict[str, dict[str, Any]] = {}
    for kind, entities in (("tag", tags), ("trigger", triggers), ("variable", variables)):
        for entity in entities:
            payload = parameters_to_dict(entity.get("parameter"))
            if kind == "trigger":
                payload = {
                    "parameter": payload,
                    "filter": entity.get("filter"),
                    "customEventFilter": entity.get("customEventFilter"),
                }
            for problem in check_references(payload, variable_names, built_in_names):
                name = problem["message"].split("`")[1].strip("{}")
                record = by_reference.setdefault(
                    name,
                    {
                        "reference": name,
                        "message": problem["message"],
                        "fix": problem["fix"],
                        "used_by": [],
                    },
                )
                record["used_by"].append(
                    {
                        "kind": kind,
                        "id": entity.get("tagId")
                        or entity.get("triggerId")
                        or entity.get("variableId"),
                        "name": entity.get("name"),
                    }
                )

    without_trigger = [
        {
            "tagId": t.get("tagId"),
            "name": t.get("name"),
            "type": t.get("type"),
            "paused": t.get("paused", False),
        }
        for t in tags
        if not t.get("firingTriggerId")
    ]

    broken = sorted(by_reference.values(), key=lambda r: -len(r["used_by"]))
    return {
        "parent": parent,
        "clean": not broken and not without_trigger,
        "broken_reference_count": len(broken),
        "affected_entity_count": sum(len(r["used_by"]) for r in broken),
        "broken_references": broken,
        "tags_without_trigger": without_trigger,
        "note": (
            "A broken reference sends an empty value, not an error. A tag with "
            "no firing trigger never executes. Neither is visible in the GTM UI."
        ),
    }


@tool_errors
def get_workspace_status(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Return the workspace changes still pending against the published version.

    Call it at the end of a create/organize session to show the user exactly
    what changed and has not been published yet.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `changes` (change type per entity) and `merge_conflicts`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    status = workspaces().getStatus(path=parent).execute()

    changes = []
    for change in status.get("workspaceChange", []):
        change_type = change.get("changeStatus")
        for entity_key in ("tag", "trigger", "variable", "folder", "builtInVariable"):
            entity = change.get(entity_key)
            if entity:
                changes.append(
                    {
                        "entity": entity_key,
                        "changeStatus": change_type,
                        "name": entity.get("name"),
                        "type": entity.get("type"),
                    }
                )
    return {
        "parent": parent,
        "count": len(changes),
        "changes": changes,
        "merge_conflicts": status.get("mergeConflict", []),
    }


# ---------------------------------------------------------------------------
# Built-in triggers
# ---------------------------------------------------------------------------

#: GTM reserves a block of trigger ids for its built-in triggers. They are NOT
#: returned by `triggers().list()` and `triggers().get()` answers 404 for them,
#: but they are valid values for `firingTriggerId`. Without this table an agent
#: has no way to attach a tag to "All Pages".
BUILT_IN_TRIGGERS = {
    "2147479553": {
        "name": "All Pages",
        "type": "pageview",
        "use_for": "Base tags that must run on every page view.",
    },
    "2147479572": {
        "name": "Consent Initialization - All Pages",
        "type": "consentInit",
        "use_for": "The CMP / Consent Mode default state. Runs before everything else.",
    },
    "2147479573": {
        "name": "Initialization - All Pages",
        "type": "init",
        "use_for": "Runs after consent initialization and before any page view tag.",
    },
}


def list_built_in_triggers() -> dict[str, Any]:
    """List the reserved GTM trigger ids (All Pages, Initialization, Consent).

    `list_triggers` does NOT return these: GTM keeps them outside the workspace
    trigger collection. They are still valid `firing_trigger_ids` values, and
    they are what you attach a Google Tag or a Conversion Linker to.

    Returns:
        A dict with `built_in_triggers` mapping id to name, type and usage.
    """
    return {
        "built_in_triggers": [
            {"triggerId": trigger_id, **details}
            for trigger_id, details in BUILT_IN_TRIGGERS.items()
        ],
        "note": (
            "Use these ids directly in `firing_trigger_ids`. Prefer "
            "Initialization (2147479573) for consent-aware base tags and "
            "All Pages (2147479553) for standard page view firing."
        ),
    }


@tool_errors
def get_container_snapshot(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Return a complete picture of the workspace in a single call.

    Combines tags, triggers, variables, built-in variables and folders, and
    computes cross-references (orphan triggers and variables, tags outside any
    folder, missing foundation tags). This is the preferred starting point for
    `auditor_agent` and `container_organizer_agent`.

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `tags`, `triggers`, `variables`, `built_in_variables`,
        `folders` and `insights`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    ws = workspaces()

    tags = paginate(ws.tags(), "list", "tag", parent=parent)
    triggers = paginate(ws.triggers(), "list", "trigger", parent=parent)
    variables = paginate(ws.variables(), "list", "variable", parent=parent)
    folders = paginate(ws.folders(), "list", "folder", parent=parent)
    built_ins = paginate(
        ws.built_in_variables(), "list", "builtInVariable", parent=parent
    )

    tag_summaries = [summarize_tag(t) for t in tags]
    trigger_summaries = [summarize_trigger(t) for t in triggers]
    variable_summaries = [summarize_variable(v) for v in variables]

    # --- Cross-references --------------------------------------------------
    used_trigger_ids: set[str] = set()
    for tag in tag_summaries:
        used_trigger_ids.update(tag.get("firingTriggerId") or [])
        used_trigger_ids.update(tag.get("blockingTriggerId") or [])

    # Variables are referenced by name, using the {{Variable name}} syntax.
    raw_blob = str(tags) + str(triggers) + str(variables)
    unused_variables = [
        v["name"]
        for v in variable_summaries
        if v["name"] and "{{%s}}" % v["name"] not in raw_blob
    ]

    orphan_triggers = [
        t["name"]
        for t in trigger_summaries
        if str(t.get("triggerId")) not in used_trigger_ids
        and t.get("type") not in ("init", "consentInit", "pageview")
    ]
    tags_without_trigger = [
        t["name"] for t in tag_summaries if not t.get("firingTriggerId")
    ]
    tags_without_folder = [
        t["name"] for t in tag_summaries if not t.get("parentFolderId")
    ]
    paused_tags = [t["name"] for t in tag_summaries if t.get("paused")]

    duplicate_names: list[str] = []
    for collection in (tag_summaries, trigger_summaries, variable_summaries):
        seen: set[str] = set()
        for item in collection:
            name = item.get("name")
            if name in seen:
                duplicate_names.append(name)
            seen.add(name)

    # --- Foundation coverage ----------------------------------------------
    present_types = {t.get("type") for t in tags if not t.get("paused")}
    missing_foundation: list[str] = []
    if present_types & {"gaawe"} and not present_types & {"googtag", "gaawc"}:
        missing_foundation.append(
            "GA4 Event tags exist but there is no Google Tag / GA4 Configuration"
        )
    if present_types & {"awct", "sp", "flc", "fls"} and "gclidw" not in present_types:
        missing_foundation.append(
            "Google Ads or Floodlight tags exist but there is no Conversion Linker"
        )

    broken_references = find_broken_references(account_id, container_id, workspace_id)

    return {
        "parent": parent,
        "totals": {
            "tags": len(tag_summaries),
            "triggers": len(trigger_summaries),
            "variables": len(variable_summaries),
            "built_in_variables": len(built_ins),
            "folders": len(folders),
        },
        "tags": tag_summaries,
        "triggers": trigger_summaries,
        "variables": variable_summaries,
        "built_in_variables": [b.get("name") for b in built_ins],
        "folders": [summarize_folder(f) for f in folders],
        "insights": {
            "broken_variable_references": broken_references.get("broken_references", []),
            "missing_foundation_tags": missing_foundation,
            "tags_without_trigger": tags_without_trigger,
            "tags_without_folder": tags_without_folder,
            "paused_tags": paused_tags,
            "orphan_triggers": orphan_triggers,
            "possibly_unused_variables": unused_variables,
            "duplicate_names": duplicate_names,
        },
    }
