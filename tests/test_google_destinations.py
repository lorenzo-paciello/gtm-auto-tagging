"""Guard destination-aware foundation checks.

An audit once reported Google Ads as fully set up in a container whose only
Google Tag pointed at GA4. The check asked "is there a googtag?" instead of "is
there one for THIS destination?", so a `G-` tag satisfied the `AW-`
requirement -- and, symmetrically, an `AW-`-only container would have reported
GA4 as covered.

A Google Tag's destination lives in the prefix of its `tagId`:

    G-   Google Analytics 4
    AW-  Google Ads
    DC-  Floodlight / Campaign Manager 360
    GT-  a Google Tag container whose destinations are configured OUTSIDE GTM

`GT-` is the honest-uncertainty case: the container cannot see what it routes
to, so the answer is "uncertain", never "present" or "missing".

Runs with pytest, or standalone: `python tests/test_google_destinations.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gtm_agent.tools.gtm_prerequisites import (  # noqa: E402
    _PRODUCT_REQUIREMENTS,
    evaluate_requirement,
    google_tag_destination,
)


def google_tag(name, destination, paused=False, trigger=True):
    return {
        "tagId": "1",
        "name": name,
        "type": "googtag",
        "paused": paused,
        "firingTriggerId": ["2147479573"] if trigger else [],
        "parameter": [{"type": "template", "key": "tagId", "value": destination}],
    }


def requirement_for(product):
    return next(
        r for r in _PRODUCT_REQUIREMENTS[product] if r["requirement"] == "base_google_tag"
    )


GA4 = requirement_for("ga4")
ADS = requirement_for("google_ads")
FLOODLIGHT = requirement_for("floodlight")


def test_ga4_tag_does_not_satisfy_google_ads():
    """The reported bug, verbatim."""
    container = [google_tag("Google Tag - GA4", "G-1234567890")]

    assert evaluate_requirement(GA4, container)["status"] == "present"

    ads = evaluate_requirement(ADS, container)
    assert ads["status"] == "missing", "a G- tag must not satisfy the AW- requirement"
    assert [t["name"] for t in ads["wrong_destination"]] == ["Google Tag - GA4"]
    assert "none targets AW-" in ads["destination_note"]


def test_ads_tag_does_not_satisfy_ga4():
    """The same fault in the other direction."""
    container = [google_tag("Google Tag - Ads", "AW-987654321")]

    assert evaluate_requirement(ADS, container)["status"] == "present"

    ga4 = evaluate_requirement(GA4, container)
    assert ga4["status"] == "missing"
    assert "none targets G-" in ga4["destination_note"]


def test_floodlight_destination_is_checked_too():
    container = [google_tag("Google Tag - GA4", "G-1")]
    result = evaluate_requirement(FLOODLIGHT, container)
    assert result["status"] == "missing"
    assert "none targets DC-" in result["destination_note"]

    covered = [google_tag("Google Tag - Floodlight", "DC-1234567")]
    assert evaluate_requirement(FLOODLIGHT, covered)["status"] == "present"


def test_both_destinations_configured():
    container = [
        google_tag("Google Tag - GA4", "G-1234567890"),
        google_tag("Google Tag - Ads", "AW-987654321"),
    ]
    assert evaluate_requirement(GA4, container)["status"] == "present"
    assert evaluate_requirement(ADS, container)["status"] == "present"


def test_gt_container_id_is_uncertain_not_present():
    """A GT- tag routes to destinations GTM cannot see. Do not guess either way."""
    container = [google_tag("Google Tag", "GT-ABCDEFG")]
    for requirement in (GA4, ADS, FLOODLIGHT):
        result = evaluate_requirement(requirement, container)
        assert result["status"] == "uncertain", requirement["label"]
        assert "configured in the Google Tag interface" in result["destination_note"]
        assert "Ask the user to confirm" in result["destination_note"]


def test_paused_and_untriggered_tags_are_distinguished():
    assert (
        evaluate_requirement(GA4, [google_tag("x", "G-1", paused=True)])["status"]
        == "present_but_paused"
    )
    assert (
        evaluate_requirement(GA4, [google_tag("x", "G-1", trigger=False)])["status"]
        == "present_but_never_fires"
    )


def test_requirements_without_prefixes_are_unaffected():
    """Conversion Linker has no destination, so every candidate counts."""
    linker = next(
        r
        for r in _PRODUCT_REQUIREMENTS["google_ads"]
        if r["requirement"] == "conversion_linker"
    )
    tags = [
        {
            "tagId": "1",
            "name": "Conversion Linker",
            "type": "gclidw",
            "paused": False,
            "firingTriggerId": ["2147479573"],
            "parameter": [],
        }
    ]
    result = evaluate_requirement(linker, tags)
    assert result["status"] == "present"
    assert result["wrong_destination"] == []


def test_destination_is_read_from_either_parameter_name():
    """`googtag` uses `tagId`; the legacy `gaawc` uses `measurementId`."""
    legacy = {
        "tagId": "2",
        "type": "gaawc",
        "name": "GA4 Config",
        "paused": False,
        "firingTriggerId": ["2147479553"],
        "parameter": [{"type": "template", "key": "measurementId", "value": "G-777"}],
    }
    assert google_tag_destination(legacy) == "G-777"
    assert evaluate_requirement(GA4, [legacy])["status"] == "present"


def test_case_insensitive_prefix():
    assert evaluate_requirement(ADS, [google_tag("x", "aw-123")])["status"] == "present"


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
