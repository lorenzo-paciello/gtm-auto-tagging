"""Sub agent for listing and inventorying the GTM container (read-only)."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...models import resolve_model
from ...prompts import LISTING_INSTRUCTION
from ...prompts import static_instruction
from ...tools import DOC_TOOLS
from ...tools import READ_TOOLS

tags_listing_agent = Agent(
    model=resolve_model("fast"),
    name="tags_listing_agent",
    description=(
        "Lists and inventories what exists in the GTM container: tags, "
        "triggers, variables, built-in variables and folders. Use it for "
        "questions like 'what do I have in the container', 'which GA4 tags "
        "exist', 'show me the configuration of tag X'. Read-only."
    ),
    instruction=static_instruction(LISTING_INSTRUCTION),
    tools=[*READ_TOOLS, *DOC_TOOLS],
)
