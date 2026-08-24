"""Sub agente de criacao de tags, acionadores e variaveis no GTM."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...config import settings
from ...prompts import CREATOR_INSTRUCTION
from ...tools import DOC_TOOLS
from ...tools import READ_TOOLS
from ...tools import WRITE_TOOLS

tags_creator_agent = Agent(
    model=settings.model_reasoning,
    name="tags_creator_agent",
    description=(
        "Cria e ajusta tags, acionadores e variaveis no workspace do GTM, "
        "seguindo a documentacao padrao de eventos (GA4, Google Ads, "
        "Floodlight, Google Tag). Use para pedidos do tipo 'crie a tag de "
        "purchase', 'implemente a conversao do Google Ads', 'preciso do evento "
        "generate_lead'. Escreve no rascunho, nunca publica."
    ),
    instruction=CREATOR_INSTRUCTION,
    tools=[*DOC_TOOLS, *READ_TOOLS, *WRITE_TOOLS],
)
