"""Guard against a tool being registered twice on one agent.

ADK warns and shadows the first copy:

    Duplicate tool name 'list_docs': the previously registered tool is
    shadowed and can no longer be called.

`SkillToolset` cannot prevent this on its own. It checks `additional_tools`
against its own four skill tools only -- it has no visibility into the agent's
permanent toolset -- so listing an already-permanent tool in a skill's
`adk_additional_tools` registers it a second time the moment the skill loads.
That is exactly what happened with `list_docs`, `read_doc` and `search_docs`.

The rule these tests enforce: `additional_tools` carries only what the agent
does NOT already have. It exists to gate a capability behind skill activation
-- `save_custom_doc` writes to `custom_docs/` and should not be reachable
otherwise -- not to re-supply tools that are always present.

Runs with pytest, or standalone: `python tests/test_tool_registry.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.tools.base_tool import BaseTool  # noqa: E402
from google.adk.tools.base_toolset import BaseToolset  # noqa: E402
from google.adk.tools.function_tool import FunctionTool  # noqa: E402

from gtm_agent.agent import root_agent  # noqa: E402


def tool_name(entry) -> str:
    if isinstance(entry, BaseTool):
        return entry.name
    return getattr(entry, "__name__", str(entry))


def permanent_tool_names(agent) -> list[str]:
    """Names the agent always carries, excluding toolsets."""
    return [tool_name(t) for t in agent.tools if not isinstance(t, BaseToolset)]


def skill_toolsets(agent):
    return [t for t in agent.tools if isinstance(t, BaseToolset) and hasattr(t, "skills")]


def all_agents():
    return [root_agent, *root_agent.sub_agents]


def test_no_agent_declares_the_same_tool_twice():
    for agent in all_agents():
        names = permanent_tool_names(agent)
        duplicates = {n for n in names if names.count(n) > 1}
        assert not duplicates, f"{agent.name} registers {duplicates} more than once"


def test_skill_additional_tools_do_not_shadow_permanent_ones():
    """The reported bug: three doc tools registered twice once the skill loaded."""
    for agent in all_agents():
        permanent = set(permanent_tool_names(agent))
        for toolset in skill_toolsets(agent):
            provided = {
                tool_name(t)
                for t in list(toolset._provided_tools_by_name.values())
            }
            collision = provided & permanent
            assert not collision, (
                f"{agent.name}: {sorted(collision)} are both permanent tools and "
                "supplied as skill additional_tools. ADK registers them twice "
                "and shadows the first copy."
            )


def test_every_skill_only_requests_tools_that_are_actually_extra():
    """A skill asking for a permanent tool is a latent duplicate registration."""
    for agent in all_agents():
        permanent = set(permanent_tool_names(agent))
        for toolset in skill_toolsets(agent):
            for skill in toolset.skills:
                requested = set(
                    skill.frontmatter.metadata.get("adk_additional_tools") or []
                )
                collision = requested & permanent
                assert not collision, (
                    f"skill '{skill.name}' declares {sorted(collision)} in "
                    "adk_additional_tools, but the agent already has them. "
                    "Remove them from the frontmatter: the skill can call a "
                    "permanent tool without being granted it."
                )


def test_skills_only_request_tools_the_toolset_can_supply():
    """A name in the frontmatter that nothing provides silently resolves to nothing."""
    for agent in all_agents():
        for toolset in skill_toolsets(agent):
            available = set(toolset._provided_tools_by_name)
            for skill in toolset.skills:
                requested = set(
                    skill.frontmatter.metadata.get("adk_additional_tools") or []
                )
                missing = requested - available
                assert not missing, (
                    f"skill '{skill.name}' requests {sorted(missing)}, which the "
                    "SkillToolset does not provide. It would resolve to nothing."
                )


def test_the_write_tool_is_gated_behind_the_skill():
    """`save_custom_doc` must NOT be permanently available anywhere."""
    for agent in all_agents():
        assert "save_custom_doc" not in permanent_tool_names(agent), (
            f"{agent.name} carries save_custom_doc permanently; writing to "
            "custom_docs/ should require activating the documentation skill."
        )

    granted = {
        name
        for agent in all_agents()
        for toolset in skill_toolsets(agent)
        for name in toolset._provided_tools_by_name
    }
    assert "save_custom_doc" in granted, "no skill can write documentation at all"


def test_every_permanent_tool_produces_a_declaration():
    """A tool the model cannot see is worse than no tool."""
    for agent in all_agents():
        for entry in agent.tools:
            if isinstance(entry, (BaseTool, BaseToolset)):
                continue
            assert FunctionTool(entry)._get_declaration() is not None, (
                f"{agent.name}: {tool_name(entry)} produced no declaration"
            )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}\n      {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
