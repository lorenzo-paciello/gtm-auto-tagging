"""Guard the instruction templating invariant.

ADK runs a string `LlmAgent.instruction` through session-state substitution on
every LLM call. Its pattern is `{+[^{}]*}+`; if the braces wrap a valid Python
identifier that is not in session state, it raises
`KeyError: Context variable not found`.

Our instructions contain GTM's `{{Variable name}}` syntax and JSON examples.
Most survive by accident, because `"error": ...` is not a valid identifier --
but `{{variable}}` and `{{Name}}` are, and each one crashed an agent mid-flow.

The fix is `static_instruction`, which turns the instruction into an
`InstructionProvider` callable so ADK skips substitution entirely. These tests
verify that every agent uses it, and that the hazard detector still recognises
the spans that would break a bare string.

Runs with pytest, or standalone: `python tests/test_prompts.py`
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.utils.instructions_utils import inject_session_state  # noqa: E402

from gtm_agent.agent import root_agent  # noqa: E402
from gtm_agent.prompts import ALL_INSTRUCTIONS  # noqa: E402
from gtm_agent.prompts import find_injection_hazards  # noqa: E402
from gtm_agent.prompts import static_instruction  # noqa: E402


def _fake_context(state: dict | None = None):
    """Minimal ReadonlyContext stand-in; only `session.state` is read."""
    session = types.SimpleNamespace(state=state or {})
    invocation = types.SimpleNamespace(session=session, artifact_service=None)
    return types.SimpleNamespace(_invocation_context=invocation)


def _all_agents():
    return [root_agent, *root_agent.sub_agents]


def test_every_agent_bypasses_state_injection():
    """No agent may pass its instruction as a bare string."""
    for agent in _all_agents():
        assert not isinstance(agent.instruction, str), (
            f"{agent.name} passes a bare string instruction. ADK will run it "
            "through session-state substitution and any {{single_word}} span "
            "will raise KeyError. Wrap it in prompts.static_instruction()."
        )
        _, bypass = asyncio.run(agent.canonical_instruction(_fake_context()))
        assert bypass is True, f"{agent.name} did not bypass state injection"


def test_instructions_survive_the_provider_unchanged():
    """GTM syntax must reach the model verbatim, not partially substituted."""
    for agent in _all_agents():
        resolved, _ = asyncio.run(agent.canonical_instruction(_fake_context()))
        assert "{{" not in resolved or "}}" in resolved
        assert len(resolved) > 500, f"{agent.name} instruction looks truncated"


def test_hazard_detector_matches_adk_behaviour():
    """find_injection_hazards must agree with what ADK actually rejects."""
    for name, text in ALL_INSTRUCTIONS.items():
        hazards = find_injection_hazards(text)
        try:
            asyncio.run(inject_session_state(text, _fake_context()))
            adk_would_crash = False
        except KeyError:
            adk_would_crash = True
        assert bool(hazards) == adk_would_crash, (
            f"{name}: detector reported {hazards!r} but ADK "
            f"{'crashed' if adk_would_crash else 'did not crash'}"
        )


def test_known_hazard_shapes():
    """Lock in which brace shapes are dangerous, so the rule stays visible."""
    dangerous = ["{{variable}}", "{{Name}}", "{{_event}}", "{var}", "{temp:x}"]
    safe = [
        "{{Variable name}}",
        "{{CONST - GA4 Measurement ID}}",
        "{{DLV - ecommerce.value}}",
        '{"error": "invalid_parameters"}',
        '{"eventName": "purchase"}',
    ]
    for span in dangerous:
        assert find_injection_hazards(span), f"{span} should be flagged"
    for span in safe:
        assert not find_injection_hazards(span), f"{span} should not be flagged"


def test_static_instruction_ignores_context():
    provider = static_instruction("hello {{world}}")
    assert provider(_fake_context()) == "hello {{world}}"
    assert provider(_fake_context({"world": "x"})) == "hello {{world}}"


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
