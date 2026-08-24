"""Sub agente de auditoria do container GTM (read-only)."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...config import settings
from ...prompts import AUDITOR_INSTRUCTION
from ...tools import DOC_TOOLS
from ...tools import READ_TOOLS
from ...tools import get_folder_map

auditor_agent = Agent(
    model=settings.model_reasoning,
    name="auditor_agent",
    description=(
        "Audita o container GTM: aderencia a documentacao padrao, cobertura de "
        "eventos, qualidade da configuracao, consentimento, nomenclatura e "
        "higiene (orfaos, duplicados, pausados). Entrega relatorio com "
        "severidade e plano de acao. Use para pedidos do tipo 'audite meu "
        "container', 'o que esta errado no meu tagueamento', 'meu GA4 esta "
        "completo?'. Somente leitura."
    ),
    instruction=AUDITOR_INSTRUCTION,
    tools=[*READ_TOOLS, *DOC_TOOLS, get_folder_map],
)
