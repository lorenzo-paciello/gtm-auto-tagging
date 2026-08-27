"""Sub agent that audits the GTM container (read-only)."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...models import resolve_model
from ...prompts import AUDITOR_INSTRUCTION
from ...prompts import static_instruction
from ...tools import DOC_TOOLS
from ...tools import READ_TOOLS
from ...tools import get_folder_map

auditor_agent = Agent(
    model=resolve_model("reasoning"),
    name="auditor_agent",
    description=(
        "Audits the GTM container: adherence to the standard documentation, "
        "foundation tags, event coverage, configuration quality, consent, "
        "naming and hygiene (orphans, duplicates, paused tags). Delivers a "
        "report with severities and an action plan. Use it for requests like "
        "'audit my container', 'what is wrong with my tagging', 'is my GA4 "
        "complete?'. Read-only."
    ),
    instruction=static_instruction(AUDITOR_INSTRUCTION),
    tools=[*READ_TOOLS, *DOC_TOOLS, get_folder_map],
)
