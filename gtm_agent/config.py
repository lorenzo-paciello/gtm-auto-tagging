"""Configuracao central do agente de auto tagging.

Todos os valores sao lidos de variaveis de ambiente (arquivo `.env` na raiz do
projeto) com fallback para defaults seguros. Nenhum modulo deve hardcodar ids de
conta/container/workspace: sempre resolver via `settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Optional

# Raiz do projeto = diretorio que contem o pacote `gtm_agent`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parent

try:  # python-dotenv vem junto com google-adk, mas nao dependemos dele.
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:  # pragma: no cover - ambiente sem python-dotenv
    pass


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "y", "on", "sim")


def _env_path(name: str, default_relative: str) -> Path:
    raw = _env(name)
    if not raw:
        return PROJECT_ROOT / default_relative
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    """Configuracao resolvida do projeto."""

    # --- Contexto GTM padrao -------------------------------------------------
    account_id: str = field(default_factory=lambda: _env("GTM_ACCOUNT_ID"))
    container_id: str = field(default_factory=lambda: _env("GTM_CONTAINER_ID"))
    workspace_id: str = field(default_factory=lambda: _env("GTM_WORKSPACE_ID", "2"))

    # --- Credenciais OAuth ---------------------------------------------------
    client_secret_file: Path = field(
        default_factory=lambda: _env_path(
            "GTM_CLIENT_SECRET_FILE", "credentials/client_secret.json"
        )
    )
    token_file: Path = field(
        default_factory=lambda: _env_path("GTM_TOKEN_FILE", "credentials/token.pickle")
    )

    # --- Documentacao --------------------------------------------------------
    default_docs_dir: Path = field(
        default_factory=lambda: _env_path("GTM_DEFAULT_DOCS_DIR", "default_docs")
    )
    custom_docs_dir: Path = field(
        default_factory=lambda: _env_path("GTM_CUSTOM_DOCS_DIR", "custom_docs")
    )
    skills_dir: Path = field(
        default_factory=lambda: _env_path("GTM_SKILLS_DIR", "gtm_agent/skills")
    )

    # --- Modelos -------------------------------------------------------------
    model_fast: str = field(
        default_factory=lambda: _env("GTM_MODEL_FAST", "gemini-3.1-flash-lite")
    )
    model_reasoning: str = field(
        default_factory=lambda: _env("GTM_MODEL_REASONING", "gemini-3.1-flash-lite")
    )

    # --- Seguranca -----------------------------------------------------------
    #: Quando True, as ferramentas de escrita nao chamam a API: apenas devolvem
    #: o payload que seria enviado. Util para revisar um plano de tagueamento.
    dry_run: bool = field(default_factory=lambda: _env_bool("GTM_DRY_RUN", False))

    # ------------------------------------------------------------------------
    def resolve_context(
        self,
        account_id: Optional[str] = None,
        container_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """Resolve o trio conta/container/workspace, com fallback para o .env.

        Raises:
            ValueError: se algum id nao puder ser resolvido.
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
                "Contexto GTM incompleto: "
                + ", ".join(missing)
                + ". Informe nos argumentos da ferramenta ou defina "
                "GTM_ACCOUNT_ID / GTM_CONTAINER_ID / GTM_WORKSPACE_ID no .env."
            )
        return resolved

    def workspace_path(
        self,
        account_id: Optional[str] = None,
        container_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> str:
        """Monta o path relativo da API para um workspace."""
        acc, cont, ws = self.resolve_context(account_id, container_id, workspace_id)
        return f"accounts/{acc}/containers/{cont}/workspaces/{ws}"


settings = Settings()
