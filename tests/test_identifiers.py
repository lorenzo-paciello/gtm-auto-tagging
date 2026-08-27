"""Guard destination-identifier consistency.

Three failures the GTM UI never surfaces, all observed in a real container:

1. A GA4 event tag carrying `G-0987654321` while the only Google Tag configures
   `G-1234567890`. Valid format, wrong property, fires happily.
2. `CONST - GA4 Measurement ID` and `CONST - GA4 Measurement id` used side by
   side. Creating the first fixed nothing for the tags referencing the second,
   and "variable not found" alone does not say the right one is a letter away.
3. A media platform whose tags disagree about the account id.

Runs with pytest, or standalone: `python tests/test_identifiers.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gtm_agent.tools.gtm_identity_audit import (  # noqa: E402
    audit_google_destinations,
)
from gtm_agent.tools.identifiers import (  # noqa: E402
    classify_destination,
    constant_values,
    find_name_collisions,
    find_near_miss_references,
    looks_like_destination,
    resolve_value,
)


def tag(tag_id, name, tag_type, params):
    return {
        "tagId": str(tag_id),
        "name": name,
        "type": tag_type,
        "paused": False,
        "firingTriggerId": ["2147479553"],
        "parameter": [
            {"type": "template", "key": k, "value": str(v)} for k, v in params.items()
        ],
    }


GOOGLE_TAG = tag(57, "Google Tag - GA4", "googtag", {"tagId": "G-1234567890"})
CONSTANTS = {"CONST - GA4 Measurement ID": "G-1234567890"}


def test_matching_destination_is_clean():
    tags = [
        GOOGLE_TAG,
        tag(65, "GA4 - Event - purchase", "gaawe",
            {"eventName": "purchase", "measurementIdOverride": "G-1234567890"}),
    ]
    assert audit_google_destinations(tags, {}) == []


def test_literal_id_with_no_base_tag_is_critical():
    """Scenario 2: a valid id that no Google Tag configures."""
    tags = [
        GOOGLE_TAG,
        tag(96, "GA4 - Event - view_item", "gaawe",
            {"eventName": "view_item", "measurementIdOverride": "G-0987654321"}),
    ]
    findings = audit_google_destinations(tags, {})
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"
    assert findings[0]["kind"] == "destination_without_base_tag"
    assert "G-0987654321" in findings[0]["message"]
    assert "Google Analytics 4" in findings[0]["message"]
    assert "G-1234567890" in findings[0]["fix"], "the fix must name the configured id"


def test_constants_are_resolved_before_comparing():
    """The tag says {{CONST - ...}}, the Google Tag says G-1234567890."""
    tags = [
        GOOGLE_TAG,
        tag(97, "GA4 - Event - select_item", "gaawe",
            {"eventName": "select_item",
             "measurementIdOverride": "{{CONST - GA4 Measurement ID}}"}),
    ]
    assert audit_google_destinations(tags, CONSTANTS) == []


def test_non_constant_variable_is_reported_as_unverifiable():
    tags = [
        GOOGLE_TAG,
        tag(98, "GA4 - Event - view_cart", "gaawe",
            {"eventName": "view_cart",
             "measurementIdOverride": "{{DLV - measurement_id}}"}),
    ]
    findings = audit_google_destinations(tags, CONSTANTS)
    assert len(findings) == 1
    assert findings[0]["kind"] == "destination_not_statically_checkable"
    assert findings[0]["severity"] == "medium"


def test_google_ads_bare_and_prefixed_forms_match():
    """`awct` stores digits only; `googtag` stores the full AW- id."""
    tags = [
        tag(85, "Google Tag - Ads", "googtag", {"tagId": "AW-123456789"}),
        tag(81, "Ads Conversion", "awct",
            {"conversionId": "123456789", "conversionLabel": "abc"}),
    ]
    assert audit_google_destinations(tags, {}) == []


def test_google_ads_genuinely_different_id_is_caught():
    tags = [
        tag(85, "Google Tag - Ads", "googtag", {"tagId": "AW-123456789"}),
        tag(81, "Ads Conversion", "awct",
            {"conversionId": "999999", "conversionLabel": "abc"}),
    ]
    findings = audit_google_destinations(tags, {})
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"


def test_a_value_that_is_not_an_id_at_all_is_called_out():
    tags = [
        GOOGLE_TAG,
        tag(99, "Broken", "gaawe",
            {"eventName": "x", "measurementIdOverride": "not-an-id"}),
    ]
    findings = audit_google_destinations(tags, {})
    assert "does not even have the shape" in findings[0]["message"]


def test_near_miss_reference_finds_the_real_variable():
    """Scenario 1: `... Measurement id` while `... Measurement ID` exists."""
    matches = find_near_miss_references(
        ["CONST - GA4 Measurement id"], ["CONST - GA4 Measurement ID", "DLV - ecommerce"]
    )
    assert len(matches) == 1
    assert matches[0]["existing"] == ["CONST - GA4 Measurement ID"]
    assert "exactly" in matches[0]["why"]


def test_near_miss_ignores_an_exact_match_and_unrelated_names():
    assert find_near_miss_references(["A"], ["A"]) == []
    assert find_near_miss_references(["Totally Other"], ["CONST - GA4"]) == []


def test_variable_name_collisions_between_existing_variables():
    collisions = find_name_collisions(
        ["CONST - GA4 Measurement ID", "CONST - GA4 Measurement id", "DLV - ecommerce"]
    )
    assert len(collisions) == 1
    assert collisions[0]["variants"] == [
        "CONST - GA4 Measurement ID",
        "CONST - GA4 Measurement id",
    ]


def test_only_constants_are_resolvable():
    variables = [
        {"name": "CONST - X", "type": "c", "parameters": {"value": "G-1"}},
        {"name": "DLV - y", "type": "v", "parameters": {"name": "ecommerce"}},
        {"name": "CJS - z", "type": "jsm", "parameters": {"javascript": "..."}},
    ]
    assert constant_values(variables) == {"CONST - X": "G-1"}


def test_resolve_value_reports_how_it_resolved():
    assert resolve_value("G-1", {}) == ("G-1", "literal")
    assert resolve_value("{{CONST - X}}", {"CONST - X": "G-1"}) == ("G-1", "constant")
    assert resolve_value("{{DLV - y}}", {}) == (None, "unresolved")
    assert resolve_value("", {}) == (None, "missing")
    assert resolve_value(None, {}) == (None, "missing")


def test_destination_classification():
    assert classify_destination("G-123") == "Google Analytics 4"
    assert classify_destination("AW-123") == "Google Ads"
    assert classify_destination("DC-123") == "Floodlight / Campaign Manager 360"
    assert classify_destination("XX-123") is None
    assert looks_like_destination("G-1234567890") is True
    assert looks_like_destination("123456") is False


def test_paused_base_tag_still_counts_as_configuring_a_destination():
    """A paused Google Tag is a separate finding; it is not a wrong id."""
    paused = dict(GOOGLE_TAG, paused=True)
    tags = [
        paused,
        tag(65, "GA4 Event", "gaawe",
            {"eventName": "x", "measurementIdOverride": "G-1234567890"}),
    ]
    assert audit_google_destinations(tags, {}) == []


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
