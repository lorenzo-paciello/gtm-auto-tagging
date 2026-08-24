"""Ferramentas de LEITURA do container GTM.

Usadas pelo `tags_listing_agent` e pelo `auditor_agent`, e tambem pelos agentes
de escrita para checar duplicidade antes de criar qualquer coisa.
"""

from __future__ import annotations

from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import get_gtm_service
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
    """Lista as contas do GTM acessiveis pelas credenciais configuradas.

    Use quando o usuario nao souber qual account_id usar.

    Returns:
        Dicionario com a chave `accounts` (accountId, name, path).
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
    """Lista os containers de uma conta do GTM.

    Args:
        account_id: id da conta. Se omitido, usa GTM_ACCOUNT_ID do .env.

    Returns:
        Dicionario com a chave `containers` (containerId, name, publicId,
        usageContext = web/amp/server/ios/android).
    """
    account = (account_id or "").strip() or settings.account_id
    if not account:
        raise ValueError("account_id nao informado e GTM_ACCOUNT_ID nao definido no .env.")
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
    """Lista os workspaces (rascunhos) de um container.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com a chave `workspaces` (workspaceId, name, description).
    """
    account = (account_id or "").strip() or settings.account_id
    container = (container_id or "").strip() or settings.container_id
    if not account or not container:
        raise ValueError("account_id/container_id nao informados e ausentes no .env.")
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
    """Lista todas as tags de um workspace do GTM.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.
        detailed: quando True devolve tambem os parametros de configuracao de
            cada tag. Use False (padrao) para inventarios e auditorias amplas,
            pois o payload completo consome muitos tokens.

    Returns:
        Dicionario com `count` e `tags`.
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
    """Retorna a configuracao COMPLETA de uma tag especifica.

    Use quando precisar inspecionar parametros, consentimento ou o corpo bruto
    de uma tag antes de replicar ou corrigir a configuracao.

    Args:
        tag_id: id numerico da tag (campo `tagId`).
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        A tag como retornada pela API, mais `parameters_flat` (parametros ja
        achatados em dicionario) para facilitar a leitura.
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
    """Lista todos os acionadores (triggers) de um workspace.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `count` e `triggers`.
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
    """Lista as variaveis definidas pelo usuario em um workspace.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `count` e `variables`.
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
    """Lista as variaveis integradas (built-in) habilitadas no workspace.

    Importante para auditoria: variaveis como Click Element, Form ID ou
    Page Path precisam estar habilitadas para que triggers e tags funcionem.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `count` e `built_in_variables` (name, type).
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
    """Lista as pastas existentes no workspace.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `count` e `folders` (folderId, name, notes).
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    folders = paginate(workspaces().folders(), "list", "folder", parent=parent)
    return {
        "parent": parent,
        "count": len(folders),
        "folders": [summarize_folder(f) for f in folders],
    }


@tool_errors
def get_workspace_status(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Retorna as alteracoes pendentes do workspace em relacao a versao publicada.

    Use ao final de uma sessao de criacao/organizacao para mostrar ao usuario
    exatamente o que mudou e ainda nao foi publicado.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `changes` (tipo de mudanca por entidade) e
        `merge_conflicts`.
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


@tool_errors
def get_container_snapshot(
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Retorna um retrato completo do workspace em uma unica chamada.

    Junta tags, triggers, variaveis, variaveis integradas e pastas, e ja
    calcula referencias cruzadas (quais triggers/variaveis estao orfaos, quais
    tags estao fora de pasta). Esta e a ferramenta preferencial do
    `auditor_agent` e do `container_organizer_agent` para comecar o trabalho.

    Args:
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Dicionario com `tags`, `triggers`, `variables`, `built_in_variables`,
        `folders` e `insights`.
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

    # --- Referencias cruzadas ---------------------------------------------
    used_trigger_ids: set[str] = set()
    for tag in tag_summaries:
        used_trigger_ids.update(tag.get("firingTriggerId") or [])
        used_trigger_ids.update(tag.get("blockingTriggerId") or [])

    # Variaveis sao referenciadas por nome, na sintaxe {{Nome da variavel}}.
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
    tags_without_folder = [t["name"] for t in tag_summaries if not t.get("parentFolderId")]
    paused_tags = [t["name"] for t in tag_summaries if t.get("paused")]

    duplicate_names: list[str] = []
    for collection in (tag_summaries, trigger_summaries, variable_summaries):
        seen: set[str] = set()
        for item in collection:
            name = item.get("name")
            if name in seen:
                duplicate_names.append(name)
            seen.add(name)

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
            "tags_without_trigger": tags_without_trigger,
            "tags_without_folder": tags_without_folder,
            "paused_tags": paused_tags,
            "orphan_triggers": orphan_triggers,
            "possibly_unused_variables": unused_variables,
            "duplicate_names": duplicate_names,
        },
    }
