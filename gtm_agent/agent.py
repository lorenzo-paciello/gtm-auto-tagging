"""Agente raiz do GTM Auto Tagging.

Coordena quatro especialistas (listagem, criacao, organizacao e auditoria) e
expoe as skills do projeto - entre elas a `default-docs-builder`, que ajuda o
usuario a escrever a propria documentacao padrao de tagueamento.
"""

from __future__ import annotations

import logging

from google.adk.agents.llm_agent import Agent
from google.adk.skills import load_skills_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from .config import settings
from .prompts import ROOT_INSTRUCTION
from .sub_agents import auditor_agent
from .sub_agents import container_organizer_agent
from .sub_agents import tags_creator_agent
from .sub_agents import tags_listing_agent
from .tools import DOC_TOOLS
from .tools import list_accounts
from .tools import list_containers
from .tools import list_workspaces
from .tools import save_custom_doc

logger = logging.getLogger(__name__)


def _build_skill_toolset() -> SkillToolset | None:
    """Carrega as skills de `gtm_agent/skills/`, se houver alguma."""
    skills_dir = settings.skills_dir
    if not skills_dir.exists():
        logger.info("Diretorio de skills nao encontrado: %s", skills_dir)
        return None
    try:
        skills = load_skills_from_dir(skills_dir)
    except Exception:  # pragma: no cover - skill malformada nao deve derrubar o agente
        logger.exception("Falha ao carregar skills de %s", skills_dir)
        return None
    if not skills:
        return None
    # `additional_tools` sao liberadas ao modelo apenas quando a skill que as
    # declara em `adk_additional_tools` e carregada via `load_skill`.
    return SkillToolset(skills=skills, additional_tools=[save_custom_doc, *DOC_TOOLS])


_skill_toolset = _build_skill_toolset()

root_agent = Agent(
    model=settings.model_reasoning,
    name="gtm_auto_tagger",
    description=(
        "Assistente de digital analytics que cria, organiza, lista e audita o "
        "tagueamento de um container Google Tag Manager (GA4, Google Ads, "
        "Floodlight, Google Tag), sempre seguindo uma documentacao padrao."
    ),
    instruction=ROOT_INSTRUCTION,
    sub_agents=[
        tags_creator_agent,
        container_organizer_agent,
        tags_listing_agent,
        auditor_agent,
    ],
    tools=[
        *DOC_TOOLS,
        list_accounts,
        list_containers,
        list_workspaces,
        *([_skill_toolset] if _skill_toolset else []),
    ],
)
