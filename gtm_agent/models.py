"""Model provider resolution.

The agents never hardcode a model. They ask this module for a *role*
(`fast` or `reasoning`) and get back whatever the `.env` says that role
should be — a Gemini model name, an Anthropic Claude client, an OpenAI model
through LiteLLM, a local Ollama model, and so on.

Set `GTM_MODEL_PROVIDER` in `.env` to switch every agent at once. See
`docs/model_providers.md` for a copy-paste block per provider.
"""

from __future__ import annotations

import logging
from typing import Any
from typing import Union

from .config import settings

logger = logging.getLogger(__name__)

Model = Union[str, Any]  # `str` for Gemini, a `BaseLlm` instance otherwise.

#: Providers that need a package the base install does not ship.
_EXTRA_DEPENDENCY = {
    "anthropic": ("anthropic", 'pip install "google-adk[extensions]"  # or: pip install anthropic'),
    "vertex_anthropic": ("anthropic", 'pip install "anthropic[vertex]"'),
    "litellm": ("litellm", "pip install litellm"),
    "openai": ("openai", 'pip install "google-adk[extensions]"  # or: pip install openai'),
}


class ModelConfigurationError(RuntimeError):
    """Raised when the configured provider cannot be built."""


def _require(provider: str) -> None:
    """Fail early, with the exact pip command, if a provider dep is missing."""
    entry = _EXTRA_DEPENDENCY.get(provider)
    if not entry:
        return
    module, install_hint = entry
    try:
        __import__(module)
    except ImportError as exc:
        raise ModelConfigurationError(
            f"GTM_MODEL_PROVIDER={provider} needs the `{module}` package, which is "
            f"not installed.\n\n    {install_hint}\n"
        ) from exc


def _anthropic(model_name: str) -> Any:
    """Claude through the Anthropic API directly (ANTHROPIC_API_KEY)."""
    _require("anthropic")
    from google.adk.models.anthropic_llm import AnthropicLlm

    # NOTE: passing a bare "claude-..." string to `Agent(model=...)` would route
    # through ADK's registry to the *Vertex AI* Claude class, which needs a GCP
    # project. Building AnthropicLlm explicitly keeps us on the Anthropic API.
    return AnthropicLlm(model=model_name, max_tokens=settings.model_max_tokens)


def _vertex_anthropic(model_name: str) -> Any:
    """Claude served from Google Cloud Vertex AI (uses GCP credentials)."""
    _require("vertex_anthropic")
    from google.adk.models.anthropic_llm import Claude

    return Claude(model=model_name, max_tokens=settings.model_max_tokens)


def _litellm(model_name: str) -> Any:
    """Any provider LiteLLM supports: openai/, azure/, ollama_chat/, bedrock/..."""
    _require("litellm")
    from google.adk.models.lite_llm import LiteLlm

    return LiteLlm(model=model_name)


_BUILDERS = {
    "google": lambda name: name,  # ADK resolves "gemini-*" names natively.
    "anthropic": _anthropic,
    "vertex_anthropic": _vertex_anthropic,
    "litellm": _litellm,
}


def resolve_model(role: str) -> Model:
    """Return the model to use for a given agent role.

    Args:
        role: "fast" for read-only agents (listing), "reasoning" for the root
            agent and the agents that plan and write.

    Returns:
        A model name (Gemini) or a configured `BaseLlm` instance.

    Raises:
        ModelConfigurationError: unknown provider, or a missing dependency.
    """
    if role not in ("fast", "reasoning"):
        raise ValueError(f"Unknown model role: {role!r}. Use 'fast' or 'reasoning'.")

    provider = settings.model_provider
    builder = _BUILDERS.get(provider)
    if builder is None:
        raise ModelConfigurationError(
            f"Unknown GTM_MODEL_PROVIDER={provider!r}. "
            f"Valid values: {', '.join(sorted(_BUILDERS))}. "
            "See docs/model_providers.md."
        )

    model_name = settings.model_fast if role == "fast" else settings.model_reasoning
    if not model_name:
        raise ModelConfigurationError(
            f"No model configured for role '{role}'. Set "
            f"GTM_MODEL_{'FAST' if role == 'fast' else 'REASONING'} in .env."
        )

    logger.debug("Resolving %s model: provider=%s name=%s", role, provider, model_name)
    return builder(model_name)


def describe_active_models() -> dict[str, str]:
    """Human-readable summary of the current model setup, for logs and the README."""
    return {
        "provider": settings.model_provider,
        "fast": settings.model_fast,
        "reasoning": settings.model_reasoning,
        "max_tokens": str(settings.model_max_tokens),
    }
