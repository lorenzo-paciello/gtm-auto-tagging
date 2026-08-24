"""Cliente autenticado da Google Tag Manager API v2 e utilitarios comuns.

Este modulo concentra autenticacao, paginacao e tratamento de erros. As
ferramentas expostas aos agentes NUNCA devem levantar excecao: elas retornam
dicionarios com a chave `error` para que o LLM possa reagir.
"""

from __future__ import annotations

import functools
import json
import logging
import pickle
from typing import Any
from typing import Callable
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import settings

logger = logging.getLogger(__name__)

#: Escopos necessarios: leitura completa + edicao de containers (rascunho).
#: `publish` NAO esta incluso de proposito: o agente nunca publica um container.
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
]


@functools.lru_cache(maxsize=1)
def get_gtm_service():
    """Retorna (e memoiza) o service autenticado da API do GTM."""
    creds = None
    token_file = settings.token_file

    if token_file.exists():
        with open(token_file, "rb") as handle:
            creds = pickle.load(handle)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not settings.client_secret_file.exists():
                raise FileNotFoundError(
                    f"client_secret.json nao encontrado em {settings.client_secret_file}. "
                    "Baixe as credenciais OAuth no Google Cloud Console e ajuste "
                    "GTM_CLIENT_SECRET_FILE no .env."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(settings.client_secret_file), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "wb") as handle:
            pickle.dump(creds, handle)

    return build("tagmanager", "v2", credentials=creds, cache_discovery=False)


def workspaces():
    """Atalho para o resource `accounts().containers().workspaces()`."""
    return get_gtm_service().accounts().containers().workspaces()


# ---------------------------------------------------------------------------
# Tratamento de erros
# ---------------------------------------------------------------------------


def _describe_http_error(exc: HttpError) -> dict[str, Any]:
    status = getattr(exc.resp, "status", None)
    detail: Any = None
    try:
        detail = json.loads(exc.content.decode("utf-8")).get("error", {})
    except Exception:  # pragma: no cover - corpo nao-JSON
        detail = exc.content.decode("utf-8", errors="replace") if exc.content else None

    hints = {
        401: "Credenciais invalidas ou expiradas. Apague o token.pickle e refaca o consentimento OAuth.",
        403: "Sem permissao para essa conta/container, ou a API do Tag Manager nao esta habilitada no projeto.",
        404: "Recurso nao encontrado. Confira account_id, container_id e workspace_id.",
        409: "Conflito: o workspace pode estar desatualizado. Rode um sync do workspace no GTM.",
        429: "Quota da API excedida. Aguarde antes de repetir (limite padrao: 0,25 req/s por usuario).",
    }
    return {
        "error": "gtm_api_error",
        "status": status,
        "message": detail if detail else str(exc),
        "hint": hints.get(status, "Consulte a mensagem retornada pela API."),
    }


def tool_errors(func: Callable) -> Callable:
    """Converte excecoes em dicionarios de erro legiveis pelo LLM."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HttpError as exc:
            logger.warning("Erro HTTP na ferramenta %s: %s", func.__name__, exc)
            return _describe_http_error(exc)
        except ValueError as exc:
            return {"error": "invalid_arguments", "message": str(exc)}
        except FileNotFoundError as exc:
            return {"error": "missing_credentials", "message": str(exc)}
        except Exception as exc:  # pragma: no cover - rede/ambiente
            logger.exception("Falha inesperada na ferramenta %s", func.__name__)
            return {
                "error": "unexpected_error",
                "message": f"{type(exc).__name__}: {exc}",
            }

    return wrapper


# ---------------------------------------------------------------------------
# Paginacao
# ---------------------------------------------------------------------------


def paginate(resource, method: str, item_key: str, **kwargs) -> list[dict[str, Any]]:
    """Percorre todas as paginas de um metodo `list` da API do GTM.

    Args:
        resource: resource ja construido (ex.: `workspaces().tags()`).
        method: nome do metodo de listagem (normalmente "list").
        item_key: chave da lista na resposta (ex.: "tag", "trigger").
        **kwargs: argumentos do metodo (ex.: `parent=...`).
    """
    items: list[dict[str, Any]] = []
    page_token: Optional[str] = None
    caller = getattr(resource, method)

    while True:
        params = dict(kwargs)
        if page_token:
            params["pageToken"] = page_token
        response = caller(**params).execute()
        items.extend(response.get(item_key, []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items


# ---------------------------------------------------------------------------
# Normalizacao de entidades (reduz tokens enviados ao modelo)
# ---------------------------------------------------------------------------


def parameters_to_dict(parameters: Optional[list[dict[str, Any]]]) -> dict[str, Any]:
    """Converte a lista `parameter` da API do GTM em um dicionario simples."""
    result: dict[str, Any] = {}
    for param in parameters or []:
        key = param.get("key")
        if not key:
            continue
        param_type = param.get("type")
        if param_type == "list":
            result[key] = [
                parameters_to_dict(item.get("map", [])) if item.get("type") == "map" else item.get("value")
                for item in param.get("list", [])
            ]
        elif param_type == "map":
            result[key] = parameters_to_dict(param.get("map", []))
        else:
            result[key] = param.get("value")
    return result


def summarize_tag(tag: dict[str, Any]) -> dict[str, Any]:
    return {
        "tagId": tag.get("tagId"),
        "name": tag.get("name"),
        "type": tag.get("type"),
        "parentFolderId": tag.get("parentFolderId"),
        "firingTriggerId": tag.get("firingTriggerId", []),
        "blockingTriggerId": tag.get("blockingTriggerId", []),
        "paused": tag.get("paused", False),
        "notes": tag.get("notes"),
        "consentSettings": tag.get("consentSettings"),
    }


def summarize_trigger(trigger: dict[str, Any]) -> dict[str, Any]:
    return {
        "triggerId": trigger.get("triggerId"),
        "name": trigger.get("name"),
        "type": trigger.get("type"),
        "parentFolderId": trigger.get("parentFolderId"),
        "customEventFilter": trigger.get("customEventFilter"),
        "filter": trigger.get("filter"),
        "notes": trigger.get("notes"),
    }


def summarize_variable(variable: dict[str, Any]) -> dict[str, Any]:
    return {
        "variableId": variable.get("variableId"),
        "name": variable.get("name"),
        "type": variable.get("type"),
        "parentFolderId": variable.get("parentFolderId"),
        "parameters": parameters_to_dict(variable.get("parameter")),
        "notes": variable.get("notes"),
    }


def summarize_folder(folder: dict[str, Any]) -> dict[str, Any]:
    return {
        "folderId": folder.get("folderId"),
        "name": folder.get("name"),
        "notes": folder.get("notes"),
    }
