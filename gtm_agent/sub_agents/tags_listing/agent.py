"""Sub agente de listagem e inventario do container GTM (read-only)."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...config import settings
from ...prompts import LISTING_INSTRUCTION
from ...tools import DOC_TOOLS
from ...tools import READ_TOOLS

tags_listing_agent = Agent(
    model=settings.model_fast,
    name="tags_listing_agent",
    description=(
        "Lista e inventaria o que existe no container GTM: tags, acionadores, "
        "variaveis, variaveis integradas e pastas. Use para perguntas do tipo "
        "'o que tenho no container', 'quais tags de GA4 existem', 'me mostre a "
        "configuracao da tag X'. Somente leitura."
    ),
    instruction=LISTING_INSTRUCTION,
    tools=[*READ_TOOLS, *DOC_TOOLS],
)
