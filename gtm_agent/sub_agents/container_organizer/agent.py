"""Sub agent that organizes the container into folders and standardizes names."""

from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from ...models import resolve_model
from ...prompts import ORGANIZER_INSTRUCTION
from ...prompts import static_instruction
from ...tools import DOC_TOOLS
from ...tools import FOLDER_TOOLS
from ...tools import READ_TOOLS
from ...tools import rename_entity

container_organizer_agent = Agent(
    model=resolve_model("reasoning"),
    name="container_organizer_agent",
    description=(
        "Organizes the GTM container: creates folders by media or function, "
        "moves tags, triggers and variables into the right folders, and "
        "standardizes naming. Use it for requests like 'organize my "
        "container', 'create folders per tool', 'standardize the tag names'."
    ),
    instruction=static_instruction(ORGANIZER_INSTRUCTION),
    tools=[*FOLDER_TOOLS, *READ_TOOLS, *DOC_TOOLS, rename_entity],
)
