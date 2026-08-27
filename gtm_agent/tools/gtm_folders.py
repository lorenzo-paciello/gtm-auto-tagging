"""Container organization tools: folders and entity movement.

Used by `container_organizer_agent`.
"""

from __future__ import annotations

from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import paginate
from .gtm_client import summarize_folder
from .gtm_client import summarize_tag
from .gtm_client import summarize_trigger
from .gtm_client import summarize_variable
from .gtm_client import tool_errors
from .gtm_client import workspaces


@tool_errors
def create_folder(
    name: str,
    notes: str = "",
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a folder in the GTM workspace.

    Run `list_folders` first: GTM happily accepts duplicate folder names, which
    destroys the organization you are trying to build.

    Args:
        name: folder name, following the project convention
            (e.g. "GA4", "Google Ads", "Floodlight", "Consent").
        notes: description of what belongs in this folder.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        The created folder, including `folderId`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    body: dict[str, Any] = {"name": name}
    if notes:
        body["notes"] = notes

    if settings.dry_run:
        return {
            "dry_run": True,
            "operation": "create_folder",
            "parent": parent,
            "body_that_would_be_sent": body,
        }

    created = workspaces().folders().create(parent=parent, body=body).execute()
    return {
        "created": True,
        "folderId": created.get("folderId"),
        "name": created.get("name"),
        "path": created.get("path"),
    }


@tool_errors
def list_folder_entities(
    folder_id: str,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """List everything already inside a folder.

    Args:
        folder_id: numeric folder id.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with the folder's `tags`, `triggers` and `variables`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    path = f"{parent}/folders/{folder_id}"

    tags: list[dict[str, Any]] = []
    triggers: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    page_token: Optional[str] = None
    folders = workspaces().folders()

    while True:
        params: dict[str, Any] = {"path": path}
        if page_token:
            params["pageToken"] = page_token
        response = folders.entities(**params).execute()
        tags.extend(response.get("tag", []))
        triggers.extend(response.get("trigger", []))
        variables.extend(response.get("variable", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return {
        "folderId": folder_id,
        "totals": {
            "tags": len(tags),
            "triggers": len(triggers),
            "variables": len(variables),
        },
        "tags": [summarize_tag(t) for t in tags],
        "triggers": [summarize_trigger(t) for t in triggers],
        "variables": [summarize_variable(v) for v in variables],
    }


@tool_errors
def move_entities_to_folder(
    folder_id: str,
    tag_ids: Optional[list[str]] = None,
    trigger_ids: Optional[list[str]] = None,
    variable_ids: Optional[list[str]] = None,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Move tags, triggers and variables into a folder.

    Args:
        folder_id: destination folder id. Use "0" to pull entities out of any
            folder and back to the container root.
        tag_ids: tag ids to move.
        trigger_ids: trigger ids to move.
        variable_ids: variable ids to move.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A summary of what was moved.
    """
    tag_ids = [str(i) for i in (tag_ids or [])]
    trigger_ids = [str(i) for i in (trigger_ids or [])]
    variable_ids = [str(i) for i in (variable_ids or [])]

    if not (tag_ids or trigger_ids or variable_ids):
        raise ValueError(
            "Provide at least one id in tag_ids, trigger_ids or variable_ids."
        )

    parent = settings.workspace_path(account_id, container_id, workspace_id)
    path = f"{parent}/folders/{folder_id}"

    if settings.dry_run:
        return {
            "dry_run": True,
            "operation": "move_entities_to_folder",
            "path": path,
            "tag_ids": tag_ids,
            "trigger_ids": trigger_ids,
            "variable_ids": variable_ids,
        }

    workspaces().folders().move_entities_to_folder(
        path=path,
        body={},
        tagId=tag_ids,
        triggerId=trigger_ids,
        variableId=variable_ids,
    ).execute()

    return {
        "moved": True,
        "folderId": folder_id,
        "moved_counts": {
            "tags": len(tag_ids),
            "triggers": len(trigger_ids),
            "variables": len(variable_ids),
        },
    }


@tool_errors
def get_folder_map(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Show the current folder tree and everything sitting outside a folder.

    The starting point for `container_organizer_agent`: one call returns the
    existing folders, how many items each holds, and the full list of entities
    with no folder (the ones that need organizing).

    Args:
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `folders` (each with its counts and contents) and `unfiled`.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    ws = workspaces()

    folders = paginate(ws.folders(), "list", "folder", parent=parent)
    tags = paginate(ws.tags(), "list", "tag", parent=parent)
    triggers = paginate(ws.triggers(), "list", "trigger", parent=parent)
    variables = paginate(ws.variables(), "list", "variable", parent=parent)

    by_folder: dict[str, dict[str, list[dict[str, Any]]]] = {
        str(f.get("folderId")): {"tags": [], "triggers": [], "variables": []}
        for f in folders
    }
    unfiled: dict[str, list[dict[str, Any]]] = {
        "tags": [],
        "triggers": [],
        "variables": [],
    }

    for kind, items, summarizer in (
        ("tags", tags, summarize_tag),
        ("triggers", triggers, summarize_trigger),
        ("variables", variables, summarize_variable),
    ):
        for item in items:
            folder_id = str(item.get("parentFolderId") or "")
            entry = summarizer(item)
            minimal = {
                "id": entry.get("tagId")
                or entry.get("triggerId")
                or entry.get("variableId"),
                "name": entry.get("name"),
                "type": entry.get("type"),
            }
            if folder_id and folder_id in by_folder:
                by_folder[folder_id][kind].append(minimal)
            else:
                unfiled[kind].append(minimal)

    return {
        "parent": parent,
        "folders": [
            {
                **summarize_folder(f),
                "counts": {
                    kind: len(items)
                    for kind, items in by_folder[str(f.get("folderId"))].items()
                },
                "contents": by_folder[str(f.get("folderId"))],
            }
            for f in folders
        ],
        "unfiled": unfiled,
        "unfiled_totals": {kind: len(items) for kind, items in unfiled.items()},
    }
