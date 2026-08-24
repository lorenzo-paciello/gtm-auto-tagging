"""Ferramentas de ESCRITA no workspace do GTM (tags, triggers e variaveis).

Regras de seguranca aplicadas aqui:

* Nada e publicado. As alteracoes ficam no workspace (rascunho) e o usuario
  publica manualmente pela interface do GTM.
* Nenhuma ferramenta apaga entidades.
* Com `GTM_DRY_RUN=true` no .env, as funcoes devolvem o payload que seria
  enviado a API sem executar a chamada.
"""

from __future__ import annotations

import json
from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import parameters_to_dict
from .gtm_client import tool_errors
from .gtm_client import workspaces

_ENTITY_RESOURCES = {
    "tag": ("tags", "tagId"),
    "trigger": ("triggers", "triggerId"),
    "variable": ("variables", "variableId"),
    "folder": ("folders", "folderId"),
}


# ---------------------------------------------------------------------------
# Conversao de configuracao "achatada" -> formato `parameter` da API do GTM
# ---------------------------------------------------------------------------


def _to_parameter(value: Any, key: Optional[str] = None) -> dict[str, Any]:
    """Converte um valor Python no objeto `Parameter` esperado pela API."""
    param: dict[str, Any] = {}
    if key is not None:
        param["key"] = key

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


def to_gtm_parameters(flat_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Converte `{"chave": valor}` na lista `parameter` da API do GTM."""
    return [_to_parameter(value, key) for key, value in flat_config.items()]


def _load_json_arg(raw: str, arg_name: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"`{arg_name}` nao e um JSON valido: {exc}. "
            'Exemplo esperado: {"measurementIdOverride": "G-XXXX", "eventName": "purchase"}'
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"`{arg_name}` deve ser um objeto JSON, nao {type(parsed).__name__}.")
    return parsed


def _dry_run_response(operation: str, parent: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "dry_run": True,
        "operation": operation,
        "parent": parent,
        "body_that_would_be_sent": body,
        "note": "GTM_DRY_RUN=true no .env. Nada foi gravado no container.",
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
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Cria uma tag no workspace do GTM.

    Antes de chamar, confirme com `list_tags` que nao existe tag equivalente e
    com `list_triggers` os ids dos acionadores. Consulte a documentacao padrao
    (`read_doc`) para o `tag_type` correto e os parametros de cada produto.

    Args:
        name: nome da tag ja no padrao de nomenclatura do projeto
            (ex.: "GA4 - Event - purchase").
        tag_type: tipo da tag na API. Ex.: "gaawe" (GA4 Event), "googtag"
            (Google Tag), "awct" (Google Ads Conversion), "flc" (Floodlight
            Counter), "fls" (Floodlight Sales), "html" (Custom HTML).
        parameters_json: string JSON com os parametros da tag em formato plano.
            Ex.: '{"eventName": "purchase", "measurementId": "{{GA4 - ID}}"}'.
            Listas e objetos aninhados sao convertidos automaticamente para o
            formato `list`/`map` da API.
        firing_trigger_ids: lista de ids de acionadores de disparo.
        blocking_trigger_ids: lista de ids de acionadores de bloqueio.
        notes: anotacoes da tag. Documente aqui a origem do requisito.
        folder_id: id da pasta de destino. Vazio deixa a tag na raiz.
        paused: cria a tag pausada. Util para revisao antes da publicacao.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        A tag criada (inclui `tagId`), ou o payload em modo dry run.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    config = _load_json_arg(parameters_json, "parameters_json")

    body: dict[str, Any] = {"name": name, "type": tag_type}
    if config:
        body["parameter"] = to_gtm_parameters(config)
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
        return _dry_run_response("create_tag", parent, body)

    created = workspaces().tags().create(parent=parent, body=body).execute()
    return {
        "created": True,
        "tagId": created.get("tagId"),
        "name": created.get("name"),
        "type": created.get("type"),
        "path": created.get("path"),
        "tagManagerUrl": created.get("tagManagerUrl"),
    }


@tool_errors
def update_tag(
    tag_id: str,
    name: str = "",
    parameters_json: str = "",
    firing_trigger_ids: Optional[list[str]] = None,
    notes: str = "",
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Atualiza uma tag existente preservando os campos nao informados.

    A API do GTM substitui a entidade inteira em um update; esta ferramenta le
    a tag atual, aplica somente as alteracoes pedidas e reenvia o corpo
    completo, usando o `fingerprint` para evitar sobrescrever mudancas feitas
    por outra pessoa no mesmo workspace.

    Args:
        tag_id: id numerico da tag.
        name: novo nome. Vazio mantem o atual.
        parameters_json: string JSON com os parametros a sobrescrever/adicionar.
            Vazio mantem os parametros atuais. Os parametros informados sao
            mesclados sobre os existentes.
        firing_trigger_ids: nova lista de acionadores de disparo. None mantem.
        notes: novas anotacoes. Vazio mantem as atuais.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        A tag atualizada, ou o payload em modo dry run.
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
        body["parameter"] = to_gtm_parameters(merged)

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
    """Cria um acionador (trigger) no workspace do GTM.

    Sempre rode `list_triggers` antes: reaproveitar um acionador existente e
    preferivel a criar um duplicado.

    Args:
        name: nome do acionador (ex.: "CE - purchase").
        trigger_type: tipo na API. Ex.: "customEvent", "pageview", "domReady",
            "windowLoaded", "click", "linkClick", "formSubmission",
            "elementVisibility", "scrollDepth", "timer", "historyChange",
            "youTubeVideo", "init", "consentInit".
        custom_event_name: obrigatorio quando trigger_type = "customEvent".
            E o nome do evento no dataLayer (ex.: "purchase"). Aceita regex se
            voce marcar `useRegex` em parameters_json.
        filters_json: string JSON com a lista de condicoes adicionais, no
            formato [{"variable": "Page Path", "operator": "contains",
            "value": "/checkout"}]. Operadores validos: equals, contains,
            startsWith, endsWith, matchRegex, cssSelector, urlMatches, greater,
            greaterOrEquals, less, lessOrEquals.
        parameters_json: string JSON com parametros extras do acionador
            (ex.: '{"verticalScrollPercentageList": "25,50,75,100"}').
        notes: anotacoes do acionador.
        folder_id: id da pasta de destino. Vazio deixa na raiz.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        O acionador criado (inclui `triggerId`), ou o payload em modo dry run.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)

    body: dict[str, Any] = {"name": name, "type": trigger_type}

    if trigger_type == "customEvent":
        if not custom_event_name:
            raise ValueError(
                "custom_event_name e obrigatorio quando trigger_type = 'customEvent'."
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
        raise ValueError(f"`filters_json` nao e um JSON valido: {exc}") from exc
    if not isinstance(filters, list):
        raise ValueError("`filters_json` deve ser uma lista de condicoes.")

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
# Variaveis
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
    """Cria uma variavel definida pelo usuario no workspace do GTM.

    Args:
        name: nome da variavel (ex.: "DLV - ecommerce.transaction_id").
        variable_type: tipo na API. Ex.: "v" (Data Layer Variable), "c"
            (Constante), "jsm" (Custom JavaScript), "j" (JavaScript Variable),
            "u" (URL), "k" (1st Party Cookie), "d" (DOM Element), "smm"
            (Lookup Table), "remm" (RegEx Table), "aev" (Auto-Event Variable).
        parameters_json: string JSON com os parametros. Exemplos:
            Data Layer Variable -> '{"name": "ecommerce.transaction_id",
            "dataLayerVersion": 2}'; Constante -> '{"value": "G-XXXXXXX"}'.
        notes: anotacoes da variavel.
        folder_id: id da pasta de destino. Vazio deixa na raiz.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        A variavel criada (inclui `variableId`), ou o payload em modo dry run.
    """
    parent = settings.workspace_path(account_id, container_id, workspace_id)
    config = _load_json_arg(parameters_json, "parameters_json")

    body: dict[str, Any] = {"name": name, "type": variable_type}
    if config:
        body["parameter"] = to_gtm_parameters(config)
    if notes:
        body["notes"] = notes
    if folder_id:
        body["parentFolderId"] = str(folder_id)

    if settings.dry_run:
        return _dry_run_response("create_variable", parent, body)

    created = workspaces().variables().create(parent=parent, body=body).execute()
    return {
        "created": True,
        "variableId": created.get("variableId"),
        "name": created.get("name"),
        "type": created.get("type"),
        "path": created.get("path"),
    }


# ---------------------------------------------------------------------------
# Renomeacao (padronizacao de nomenclatura)
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
    """Renomeia uma tag, acionador, variavel ou pasta preservando a configuracao.

    Use para aplicar a convencao de nomenclatura do projeto sem recriar
    entidades. ATENCAO: renomear uma variavel NAO atualiza as referencias
    `{{Nome antigo}}` espalhadas pelo container - verifique os usos antes.

    Args:
        entity_type: "tag", "trigger", "variable" ou "folder".
        entity_id: id numerico da entidade.
        new_name: novo nome, ja no padrao de nomenclatura.
        account_id: id da conta. Se omitido, usa o valor do .env.
        container_id: id do container. Se omitido, usa o valor do .env.
        workspace_id: id do workspace. Se omitido, usa o valor do .env.

    Returns:
        Confirmacao com nome antigo e novo, ou o payload em modo dry run.
    """
    if entity_type not in _ENTITY_RESOURCES:
        raise ValueError(
            f"entity_type invalido: '{entity_type}'. Use um de: "
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
