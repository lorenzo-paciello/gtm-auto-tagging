"""Sub agent that creates tags, triggers and variables in GTM."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...models import resolve_model
from ...prompts import CREATOR_INSTRUCTION
from ...prompts import static_instruction
from ...tools import DOC_TOOLS
from ...tools import READ_TOOLS
from ...tools import WRITE_TOOLS

tags_creator_agent = Agent(
    model=resolve_model("reasoning"),
    name="tags_creator_agent",
    description=(
        "Creates and adjusts tags, triggers and variables in the GTM "
        "workspace, following the standard event documentation (GA4, Google "
        "Ads, Floodlight, Google Tag) and verifying foundation tags first. Use "
        "it for requests like 'create the purchase tag', 'implement the Google "
        "Ads conversion', 'I need the generate_lead event'. Writes to the "
        "draft, never publishes."
    ),
    instruction=static_instruction(CREATOR_INSTRUCTION),
    tools=[*DOC_TOOLS, *READ_TOOLS, *WRITE_TOOLS],
)
