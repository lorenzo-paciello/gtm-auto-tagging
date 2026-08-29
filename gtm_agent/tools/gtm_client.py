"""Authenticated Google Tag Manager API v2 client and shared helpers.

This module owns authentication, pagination and error handling. Tools exposed
to the agents must NEVER raise: they return dictionaries carrying an `error`
key so the model can react to the failure.
"""

from __future__ import annotations

import functools
import json
import logging
import pickle
import random
import time
from typing import Any
from typing import Callable
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..config import settings

logger = logging.getLogger(__name__)

#: Full read access plus container editing (draft only).
#: `publish` is deliberately absent: the agent never publishes a container.
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
]


@functools.lru_cache(maxsize=1)
def get_gtm_service():
    """Return (and memoize) the authenticated GTM API service."""
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
                    f"client_secret.json not found at {settings.client_secret_file}. "
                    "Download the OAuth credentials from the Google Cloud Console "
                    "and point GTM_CLIENT_SECRET_FILE at them in .env."
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
    """Shortcut for the `accounts().containers().workspaces()` resource."""
    return get_gtm_service().accounts().containers().workspaces()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def _describe_http_error(exc: HttpError) -> dict[str, Any]:
    status = getattr(exc.resp, "status", None)
    detail: Any = None
    try:
        detail = json.loads(exc.content.decode("utf-8")).get("error", {})
    except Exception:  # pragma: no cover - non-JSON body
        detail = exc.content.decode("utf-8", errors="replace") if exc.content else None

    hints = {
        401: "Invalid or expired credentials. Delete token.pickle and redo the OAuth consent.",
        403: "No permission for this account/container, or the Tag Manager API is not enabled on the project.",
        404: "Resource not found. Check account_id, container_id and workspace_id.",
        409: "Conflict: the workspace may be stale. Sync the workspace in the GTM UI.",
        429: "API quota exceeded. Wait before retrying (default limit: 0.25 requests/second per user).",
    }
    return {
        "error": "gtm_api_error",
        "status": status,
        "message": detail if detail else str(exc),
        "hint": hints.get(status, "Read the message returned by the API."),
    }


#: The Tag Manager API allows roughly 0.25 queries/second per user. A tool that
#: fans out (a snapshot reads five collections) trips that easily, and the
#: agent has no useful way to recover from a raw 429.
_MAX_RETRIES = 4
_BASE_BACKOFF = 2.0


def _is_retryable(exc: HttpError) -> bool:
    status = getattr(exc.resp, "status", None)
    return status == 429 or (status is not None and status >= 500)


def tool_errors(func: Callable) -> Callable:
    """Retry rate limits, then turn exceptions into model-readable dicts."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            for attempt in range(_MAX_RETRIES):
                try:
                    return func(*args, **kwargs)
                except HttpError as exc:
                    if not _is_retryable(exc) or attempt == _MAX_RETRIES - 1:
                        raise
                    delay = _BASE_BACKOFF * (2**attempt) + random.uniform(0, 1)
                    logger.info(
                        "Retryable API error in %s (attempt %d/%d), sleeping %.1fs",
                        func.__name__,
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
        except HttpError as exc:
            logger.warning("HTTP error in tool %s: %s", func.__name__, exc)
            return _describe_http_error(exc)
        except ValueError as exc:
            return {"error": "invalid_arguments", "message": str(exc)}
        except FileNotFoundError as exc:
            return {"error": "missing_credentials", "message": str(exc)}
        except Exception as exc:  # pragma: no cover - network/environment
            logger.exception("Unexpected failure in tool %s", func.__name__)
            return {
                "error": "unexpected_error",
                "message": f"{type(exc).__name__}: {exc}",
            }

    return wrapper


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def paginate(resource, method: str, item_key: str, **kwargs) -> list[dict[str, Any]]:
    """Walk every page of a GTM API `list` method.

    Args:
        resource: an already built resource (e.g. `workspaces().tags()`).
        method: the listing method name (normally "list").
        item_key: the list key in the response (e.g. "tag", "trigger").
        **kwargs: method arguments (e.g. `parent=...`).
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
# Entity normalization (keeps the token cost of inventories down)
# ---------------------------------------------------------------------------


def parameters_to_dict(parameters: Optional[list[dict[str, Any]]]) -> dict[str, Any]:
    """Flatten the GTM API `parameter` list into a plain dictionary."""
    result: dict[str, Any] = {}
    for param in parameters or []:
        key = param.get("key")
        if not key:
            continue
        param_type = param.get("type")
        if param_type == "list":
            result[key] = [
                parameters_to_dict(item.get("map", []))
                if item.get("type") == "map"
                else item.get("value")
                for item in param.get("list", [])
            ]
        elif param_type == "map":
            result[key] = parameters_to_dict(param.get("map", []))
        else:
            result[key] = param.get("value")
    return result


#: How GTM's settings tables name their two columns. A Google Tag writes
#: `{parameter, parameterValue}`, a GA4 Configuration writes `{name, value}`,
#: and templates use whichever their author chose.
_SETTING_COLUMNS = (
    ("parameter", "parameterValue"),
    ("name", "value"),
    ("fieldName", "value"),
    ("key", "value"),
)


def setting_values(flat: dict[str, Any]) -> dict[str, str]:
    """Settings held in a tag's nested tables, flattened to `name -> value`.

    Half a tag's real configuration is not in its top-level parameters. A
    Google Tag keeps `send_page_view` in `configSettingsTable`, a list of
    `{parameter, parameterValue}` rows; a GA4 Configuration keeps the same
    thing in `fieldsToSet` as `{name, value}`. Reading only the top level
    misses them entirely -- which made the agent tell a user that a page_view
    event tag would double-count, on a property where they had just turned
    `send_page_view` off.

    Later rows win, matching how GTM applies them.
    """
    settings: dict[str, str] = {}
    for value in flat.values():
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, dict):
                continue
            for name_key, value_key in _SETTING_COLUMNS:
                name = row.get(name_key)
                if isinstance(name, str) and name and value_key in row:
                    settings[name] = str(row[value_key])
                    break
    return settings


def scalar_values(value: Any) -> list[str]:
    """Every string anywhere in a flattened parameter tree.

    An account id can sit in a nested settings row as easily as in a top-level
    parameter, and a search that only reads the top level quietly misses it.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [v for item in value.values() for v in scalar_values(item)]
    if isinstance(value, list):
        return [v for item in value for v in scalar_values(item)]
    return []


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
