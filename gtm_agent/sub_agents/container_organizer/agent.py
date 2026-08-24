"""Sub agente de organizacao do container em pastas e padronizacao de nomes."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...config import settings
from ...prompts import ORGANIZER_INSTRUCTION
from ...tools import DOC_TOOLS
from ...tools import FOLDER_TOOLS
from ...tools import READ_TOOLS
from ...tools import rename_entity

container_organizer_agent = Agent(
    model=settings.model_reasoning,
    name="container_organizer_agent",
    description=(
        "Organiza o container GTM: cria pastas por midia ou funcao, move tags, "
        "acionadores e variaveis para as pastas certas e padroniza a "
        "nomenclatura. Use para pedidos do tipo 'organize meu container', "
        "'crie pastas por ferramenta', 'padronize os nomes das tags'."
    ),
    instruction=ORGANIZER_INSTRUCTION,
    tools=[*FOLDER_TOOLS, *READ_TOOLS, *DOC_TOOLS, rename_entity],
)
