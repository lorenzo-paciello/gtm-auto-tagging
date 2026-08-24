"""Ferramentas de organizacao do container: pastas e movimentacao de entidades.

Usadas pelo `container_organizer_agent`.
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
    """Cria uma pasta no workspace do GTM.

    Rode `list_folders` antes: o GTM aceita pastas com nomes repetidos, o que
    quebra a organizacao.

    Args:
        name: nome da pasta, seguindo a convencao do projeto
            (ex.: "GA4", "Google Ads", "Floodlight", "Consentimento").
        notes: descricao do que pertence a esta pasta.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        A pasta criada, incluindo `folderId`.
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
    """Lista tudo que ja esta dentro de uma pasta.

    Args:
        folder_id: id numerico da pasta.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `tags`, `triggers` e `variables` da pasta.
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
    """Move tags, acionadores e variaveis para uma pasta.

    Args:
        folder_id: id da pasta de destino. Use "0" para tirar as entidades de
            qualquer pasta e devolve-las a raiz do container.
        tag_ids: ids das tags a mover.
        trigger_ids: ids dos acionadores a mover.
        variable_ids: ids das variaveis a mover.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Resumo do que foi movido.
    """
    tag_ids = [str(i) for i in (tag_ids or [])]
    trigger_ids = [str(i) for i in (trigger_ids or [])]
    variable_ids = [str(i) for i in (variable_ids or [])]

    if not (tag_ids or trigger_ids or variable_ids):
        raise ValueError(
            "Informe ao menos um id em tag_ids, trigger_ids ou variable_ids."
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
    """Mostra a arvore atual de pastas e o que esta fora de qualquer pasta.

    Ponto de partida do `container_organizer_agent`: em uma chamada devolve as
    pastas existentes, a contagem de itens em cada uma e a lista completa das
    entidades sem pasta (as que precisam ser organizadas).

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `folders` (cada uma com sua contagem) e `unfiled`.
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
                "id": entry.get("tagId") or entry.get("triggerId") or entry.get("variableId"),
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
