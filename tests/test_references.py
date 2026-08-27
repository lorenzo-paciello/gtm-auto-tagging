"""Guard `{{Variable}}` reference integrity and firing-trigger presence.

Both failures are silent in GTM. An unknown `{{Name}}` resolves to an EMPTY
STRING at runtime -- the tag fires, the UI looks correct, and the value sent is
blank. A tag with no firing trigger simply never runs. The API accepts both
without comment.

One agent run created ten GA4 ecommerce tags all pointing at
`{{CONST - GA4 Measurement ID}}`, a variable that was never created, plus two
base tags with no trigger. Nothing reported anything.

Runs with pytest, or standalone: `python tests/test_references.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gtm_agent.tools.references import (  # noqa: E402
    RESERVED_REFERENCES,
    built_in_variable_names,
    check_references,
    extract_references,
)

USER_VARIABLES = ["DLV - ecommerce", "CONST - GA4 Measurement ID"]
ENABLED_BUILT_INS = ["Page URL", "Page Path", "Event"]


def test_references_are_found_anywhere_in_a_payload():
    payload = {
        "tagId": "{{CONST - GA4 Measurement ID}}",
        "table": [{"parameter": "value", "parameterValue": "{{DLV - ecommerce}}"}],
        "html": "<script>var u = {{Page URL}};</script>",
        "plain": "no references here",
    }
    assert extract_references(payload) == {
        "CONST - GA4 Measurement ID",
        "DLV - ecommerce",
        "Page URL",
    }


def test_known_variables_pass():
    payload = {"a": "{{DLV - ecommerce}}", "b": "{{Page URL}}"}
    assert check_references(payload, USER_VARIABLES, ENABLED_BUILT_INS) == []


def test_the_reported_failure_is_caught():
    """Ten tags once shipped with this exact reference and no such variable."""
    payload = {"measurementIdOverride": "{{CONST - GA4 Measurement ID}}"}
    problems = check_references(payload, ["DLV - ecommerce"], ENABLED_BUILT_INS)
    assert len(problems) == 1
    assert problems[0]["severity"] == "error"
    assert "EMPTY STRING" in problems[0]["message"]
    assert "create_variable" in problems[0]["fix"]


def test_a_disabled_built_in_gets_a_different_fix():
    """Creating a user variable named 'Click Text' would shadow the built-in."""
    problems = check_references(
        {"html": "{{Click Text}}"}, USER_VARIABLES, ENABLED_BUILT_INS
    )
    assert len(problems) == 1
    assert "built-in variable that is NOT enabled" in problems[0]["message"]
    assert "Do NOT create a user variable" in problems[0]["fix"]


def test_built_in_names_come_from_the_api_discovery_document():
    names = built_in_variable_names()
    assert len(names) > 100, "the discovery document should list every built-in"
    for expected in ("pageurl", "clicktext", "formid", "scrolldepththreshold"):
        assert expected in names, expected


def test_display_names_and_enum_names_normalize_together():
    """'Page URL' in a reference and `pageUrl` in the enum are the same thing."""
    problems = check_references({"a": "{{Page Hostname}}"}, [], ["Page Hostname"])
    assert problems == []


def test_reserved_internal_names_are_not_reported():
    """`{{_event}}` is what create_trigger writes into a custom-event filter."""
    payload = {"arg0": "{{_event}}", "arg1": "purchase"}
    assert check_references(payload, [], []) == []
    assert "_event" in RESERVED_REFERENCES


def test_empty_and_reference_free_payloads_are_cheap():
    for payload in (None, {}, {"a": "plain text"}, [], ""):
        assert extract_references(payload) == set()
        assert check_references(payload, [], []) == []


def test_every_missing_reference_is_reported_once_each():
    payload = {"a": "{{Missing One}}", "b": "{{Missing One}} {{Missing Two}}"}
    problems = check_references(payload, [], [])
    assert len(problems) == 2
    assert {p["message"].split("`")[1] for p in problems} == {
        "{{Missing One}}",
        "{{Missing Two}}",
    }


def test_whitespace_inside_a_reference_is_tolerated():
    assert extract_references("{{ Page URL }}") == {"Page URL"}
    assert check_references("{{ Page URL }}", [], ["Page URL"]) == []


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
