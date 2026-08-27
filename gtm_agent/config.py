"""Central configuration for the auto-tagging agent.

Every value comes from environment variables (the `.env` file at the project
root) with safe fallbacks. No module should hardcode account, container or
workspace ids: always resolve them through `settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Optional

# Project root = the directory that contains the `gtm_agent` package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent

try:  # python-dotenv ships with google-adk, but we do not depend on it.
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:  # pragma: no cover - environment without python-dotenv
    pass


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_path(name: str, default_relative: str) -> Path:
    raw = _env(name)
    if not raw:
        return PROJECT_ROOT / default_relative
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    """Resolved project configuration."""

    # --- Default GTM context -------------------------------------------------
    account_id: str = field(default_factory=lambda: _env("GTM_ACCOUNT_ID"))
    container_id: str = field(default_factory=lambda: _env("GTM_CONTAINER_ID"))
    workspace_id: str = field(default_factory=lambda: _env("GTM_WORKSPACE_ID", "2"))

    # --- OAuth credentials ---------------------------------------------------
    client_secret_file: Path = field(
        default_factory=lambda: _env_path(
            "GTM_CLIENT_SECRET_FILE", "credentials/client_secret.json"
        )
    )
    token_file: Path = field(
        default_factory=lambda: _env_path("GTM_TOKEN_FILE", "credentials/token.pickle")
    )

    # --- Documentation -------------------------------------------------------
    default_docs_dir: Path = field(
        default_factory=lambda: _env_path("GTM_DEFAULT_DOCS_DIR", "default_docs")
    )
    custom_docs_dir: Path = field(
        default_factory=lambda: _env_path("GTM_CUSTOM_DOCS_DIR", "custom_docs")
    )
    skills_dir: Path = field(
        default_factory=lambda: _env_path("GTM_SKILLS_DIR", "gtm_agent/skills")
    )

    # --- Models --------------------------------------------------------------
    #: google | anthropic | vertex_anthropic | litellm
    #: See docs/model_providers.md for a copy-paste block per provider.
    model_provider: str = field(
        default_factory=lambda: _env("GTM_MODEL_PROVIDER", "google").lower()
    )
    #: Model for the read-only agents (listing). Cheap and fast is enough.
    model_fast: str = field(
        default_factory=lambda: _env("GTM_MODEL_FAST", "gemini-3.1-flash-lite")
    )
    #: Model for the root agent and the agents that plan and write.
    model_reasoning: str = field(
        default_factory=lambda: _env("GTM_MODEL_REASONING", "gemini-3.1-flash-lite")
    )
    #: Output token cap. Only applies to the Anthropic providers; Gemini and
    #: LiteLLM use their own defaults. Audit reports are long, so keep headroom.
    model_max_tokens: int = field(
        default_factory=lambda: _env_int("GTM_MODEL_MAX_TOKENS", 16000)
    )

    # --- Safety --------------------------------------------------------------
    #: When True, write tools never call the API: they return the payload that
    #: would have been sent. Useful for reviewing a tagging plan.
    dry_run: bool = field(default_factory=lambda: _env_bool("GTM_DRY_RUN", False))

    # ------------------------------------------------------------------------
    def resolve_context(
        self,
        account_id: Optional[str] = None,
        container_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """Resolve the account/container/workspace triple, falling back to `.env`.

        Raises:
            ValueError: if any id cannot be resolved.
        """
        resolved = (
            (account_id or "").strip() or self.account_id,
            (container_id or "").strip() or self.container_id,
            (workspace_id or "").strip() or self.workspace_id,
        )
        missing = [
            name
            for name, value in zip(
                ("account_id", "container_id", "workspace_id"), resolved
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Incomplete GTM context: "
                + ", ".join(missing)
                + ". Pass them as tool arguments, or set GTM_ACCOUNT_ID / "
                "GTM_CONTAINER_ID / GTM_WORKSPACE_ID in .env."
            )
        return resolved

    def workspace_path(
        self,
        account_id: Optional[str] = None,
        container_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> str:
        """Build the API relative path for a workspace."""
        acc, cont, ws = self.resolve_context(account_id, container_id, workspace_id)
        return f"accounts/{acc}/containers/{cont}/workspaces/{ws}"


settings = Settings()
