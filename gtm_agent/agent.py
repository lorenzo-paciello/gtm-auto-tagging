"""Root agent for GTM Auto Tagging.

Coordinates four specialists (listing, creation, organization and auditing) and
exposes the project skills -- among them `default-docs-builder`, which helps the
user write their own standard tagging documentation.
"""

from __future__ import annotations

import logging

from google.adk.agents.llm_agent import Agent
from google.adk.apps.app import App
from google.adk.skills import load_skills_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from .config import settings
from .models import describe_active_models
from .models import resolve_model
from .prompts import ROOT_INSTRUCTION
from .prompts import static_instruction
from .sub_agents import auditor_agent
from .sub_agents import container_organizer_agent
from .sub_agents import tags_creator_agent
from .sub_agents import tags_listing_agent
from .tools import DOC_TOOLS
from .tools import list_accounts
from .tools import list_containers
from .tools import list_workspaces
from .tools import save_custom_doc
from .usage import UsageTrackerPlugin

logger = logging.getLogger(__name__)


def _build_skill_toolset() -> SkillToolset | None:
    """Load the skills from `gtm_agent/skills/`, if there are any."""
    skills_dir = settings.skills_dir
    if not skills_dir.exists():
        logger.info("Skills directory not found: %s", skills_dir)
        return None
    try:
        skills = load_skills_from_dir(skills_dir)
    except Exception:  # pragma: no cover - a malformed skill must not break the agent
        logger.exception("Failed to load skills from %s", skills_dir)
        return None
    if not skills:
        return None
    # `additional_tools` are only released to the model once the skill that
    # declares them in `adk_additional_tools` is loaded via `load_skill`. It
    # must therefore list ONLY tools the agent does not already carry:
    # SkillToolset checks for collisions against its own four skill tools, not
    # against the agent's, so re-supplying a permanent tool registers it twice
    # and the LLM request shadows the first copy.
    #
    # `save_custom_doc` qualifies -- write access to custom_docs/ should exist
    # only while the documentation skill is active. The doc *read* tools are
    # permanent on the root agent, so the skill can already call them.
    return SkillToolset(skills=skills, additional_tools=[save_custom_doc])


_skill_toolset = _build_skill_toolset()

logger.info("Active models: %s", describe_active_models())

root_agent = Agent(
    model=resolve_model("reasoning"),
    name="gtm_auto_tagger",
    description=(
        "A digital analytics assistant that creates, organizes, lists and "
        "audits the tagging of a Google Tag Manager container (GA4, Google "
        "Ads, Floodlight, Google Tag), always following a standard "
        "documentation set."
    ),
    instruction=static_instruction(ROOT_INSTRUCTION),
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


# `adk web` and `adk run` look for `app` before `root_agent`, so exporting an
# App is what registers the usage tracker across every sub agent. `root_agent`
# stays exported for direct imports and for tests.
app = App(
    name="gtm_auto_tagger",
    root_agent=root_agent,
    plugins=[UsageTrackerPlugin()],
)
