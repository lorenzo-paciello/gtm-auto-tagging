"""Guard third-party media detection against false positives.

A container with one Google Tag and one Pinterest event tag once reported
"duplicate base setup tags detected for Pinterest and Microsoft Advertising"
-- for platforms that had one tag and zero tags respectively. Three separate
faults combined to produce it, and each is locked down here:

1. `tagId` is claimed by Pinterest, by Microsoft UET *and* by Google's own
   `googtag`, yet a single parameter-name hit was enough to attribute a tag.
2. Native Google tag types were matched against third-party signatures at all.
3. Event tags were classified as setup tags, so every purchase tag looked like
   a second base pixel.

Runs with pytest, or standalone: `python tests/test_media_detection.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gtm_agent.tools.gtm_prerequisites import (  # noqa: E402
    _detect_media_platforms,
    evaluate_consent_initialization,
)
from gtm_agent.tools.gtm_templates import (  # noqa: E402
    parse_template_parameters,
    template_role_hints,
)
from gtm_agent.tools.gtm_templates import template_bootstraps_library  # noqa: E402
from gtm_agent.tools.media_platforms import ambiguous_id_parameters  # noqa: E402


def tag(tag_id, name, tag_type, params=None, paused=False):
    return {
        "tagId": str(tag_id),
        "name": name,
        "type": tag_type,
        "paused": paused,
        "firingTriggerId": ["2147479553"],
        "parameter": [
            {"type": "template", "key": k, "value": str(v)}
            for k, v in (params or {}).items()
        ],
    }


_NEWLINE = chr(10)  # avoids escape sequences in this file entirely


def _template_data(gallery_id, params_json='[]', permissions='[]'):
    """Build a .tpl document for tests."""
    return _NEWLINE.join([
        "___INFO___",
        "",
        '{"type": "TAG", "id": "cvt_%s"}' % gallery_id,
        "",
        "___TEMPLATE_PARAMETERS___",
        "",
        params_json,
        "",
        "___WEB_PERMISSIONS___",
        "",
        permissions,
        "",
    ])


def gallery_template(template_id, name, owner, gallery_id, injects=False, params=None):
    import json as _json

    permissions = (
        '[{"instance": {"key": {"publicId": "inject_script"}}}]'
        if injects
        else '[]'
    )
    return {
        "templateId": str(template_id),
        "containerId": "261951688",
        "name": name,
        "galleryReference": {"owner": owner, "galleryTemplateId": gallery_id},
        "templateData": _template_data(
            gallery_id, _json.dumps(params or []), permissions
        ),
    }


def _param(name, required=False):
    entry = {"type": "TEXT", "name": name, "simpleValueType": True}
    if required:
        entry["valueValidators"] = [{"type": "NON_EMPTY"}]
    return entry


# Parameters mirror what the real gallery templates declare.
TEMPLATES = [
    gallery_template(
        51, "Pinterest Pixel Tag", "pinterest", "NGMPN", injects=True,
        params=[_param("tagId", True), _param("eventName"), _param("adeEventName", True)],
    ),
    gallery_template(
        52, "Meta Pixel", "facebook", "5RM3Q", injects=True,
        params=[_param("pixelId", True), _param("eventName")],
    ),
    gallery_template(
        54, "TikTok Pixel", "tiktok", "MRQN8", injects=False,
        params=[_param("pixel_code"), _param("event")],
    ),
]

# The exact container that produced the false duplicate report.
REPORTED_CASE = [
    tag(57, "Google Tag - GA4", "googtag", {"tagId": "G-1234567890"}),
    tag(64, "Google Ads - Conversion Linker", "gclidw"),
    tag(65, "GA4 - Event - purchase", "gaawe", {"eventName": "purchase"}),
    tag(68, "Pinterest - Event - Checkout", "cvt_NGMPN",
        {"tagId": "2612427802921", "eventName": "checkout"}),
]


def test_google_tag_is_not_a_pinterest_or_microsoft_base_pixel():
    """The reported bug, verbatim."""
    found = _detect_media_platforms(REPORTED_CASE, TEMPLATES)

    assert "microsoft_ads" not in found, (
        "Microsoft Advertising was detected in a container with no Microsoft "
        f"tag: {found.get('microsoft_ads')}"
    )
    everything = [
        entry
        for platform in found.values()
        for bucket in platform.values()
        for entry in bucket
    ]
    assert not [e for e in everything if e["name"] == "Google Tag - GA4"], (
        "The Google Tag was attributed to a third-party platform"
    )


def test_pinterest_purchase_tag_is_an_event_not_a_duplicate_base():
    found = _detect_media_platforms(REPORTED_CASE, TEMPLATES)
    pinterest = found["pinterest"]
    assert len(pinterest["setup_tags"]) == 0, (
        f"event tag classified as setup: {pinterest['setup_tags']}"
    )
    assert [e["name"] for e in pinterest["event_tags"]] == [
        "Pinterest - Event - Checkout"
    ]


def test_native_google_types_are_never_media_tags():
    natives = [
        tag(1, "Google Tag", "googtag", {"tagId": "G-1"}),
        tag(2, "Ads Conversion", "awct", {"conversionId": "1", "conversionLabel": "x"}),
        tag(3, "Floodlight", "flc", {"advertiserId": "1234567"}),
        tag(4, "GA4 Event", "gaawe", {"eventName": "purchase"}),
    ]
    assert _detect_media_platforms(natives, TEMPLATES) == {}


def test_ambiguous_parameter_alone_proves_nothing():
    """`tagId` is shared by three platforms; on its own it is not evidence."""
    assert "tagId" in ambiguous_id_parameters()
    assert "pixelId" in ambiguous_id_parameters()
    assert "advertiserId" in ambiguous_id_parameters()
    # `pixel_code` belongs to TikTok alone, so it stays usable as a signal.
    assert "pixel_code" not in ambiguous_id_parameters()

    anonymous = [tag(9, "Some Third Party Tag", "html", {"tagId": "123"})]
    assert _detect_media_platforms(anonymous, TEMPLATES) == {}


def test_specific_parameter_plus_name_is_enough():
    """Two weak signals attribute the tag, at medium confidence."""
    custom = [tag(9, "TikTok Base Pixel", "html", {"pixel_code": "CABC123"})]
    found = _detect_media_platforms(custom, TEMPLATES)
    entry = found["tiktok"]["setup_tags"][0]
    assert entry["confidence"] == "medium"
    assert len(entry["signals"]) == 2


def test_html_base_snippet_is_a_strong_signal():
    html = [
        tag(9, "Anonymous script", "html", {"html": "fbq('init', '156914648903155');"})
    ]
    found = _detect_media_platforms(html, TEMPLATES)
    entry = found["meta"]["setup_tags"][0]
    assert entry["confidence"] == "high"


def test_a_pixel_id_that_is_a_gtm_variable_is_still_recognised():
    """Hand-written pixels are usually parameterised, not hardcoded."""
    html = [
        tag(
            9,
            "Anonymous script",
            "html",
            {"html": "fbq('init', '{{CONST - Meta Pixel ID}}'); fbq('track','PageView');"},
        )
    ]
    found = _detect_media_platforms(html, TEMPLATES)
    assert found["meta"]["setup_tags"][0]["confidence"] == "high"


def test_an_implausible_id_is_not_a_pixel():
    """`fbq('init', '123')` is a snippet someone was drafting, not a pixel."""
    html = [tag(9, "Draft", "html", {"html": "fbq('init', '123');"})]
    assert "meta" not in _detect_media_platforms(html, TEMPLATES)


def test_template_bootstrap_detection():
    """Whether a missing base tag is fatal depends on the template itself."""
    by_name = {t["name"]: t for t in TEMPLATES}
    assert template_bootstraps_library(by_name["Meta Pixel"]) is True
    assert template_bootstraps_library(by_name["Pinterest Pixel Tag"]) is True
    assert template_bootstraps_library(by_name["TikTok Pixel"]) is False


def test_unclear_tags_are_not_assumed_to_be_setup_tags():
    """No event parameter set and no base keyword: report unclear, do not guess."""
    tags = [tag(9, "Meta Thing", "cvt_5RM3Q", {"pixelId": "123"})]
    meta = _detect_media_platforms(tags, TEMPLATES)["meta"]
    assert meta["setup_tags"] == []
    assert meta["event_tags"] == []
    assert len(meta["unclassified"]) == 1


def parametered_template(template_id, name, owner, gallery_id, params):
    """A gallery template that declares real parameters."""
    import json as _json

    return {
        "templateId": str(template_id),
        "containerId": "261951688",
        "name": name,
        "galleryReference": {"owner": owner, "galleryTemplateId": gallery_id},
        "templateData": _template_data(gallery_id, _json.dumps(params)),
    }


# Real declarations, read from the installed gallery templates.
CRITEO_TEMPLATE = parametered_template(
    91, "Criteo Loader - Official", "criteo", "KT9RV",
    [
        {"type": "TEXT", "name": "partnerType", "simpleValueType": True},
        {"type": "TEXT", "name": "partnerId", "simpleValueType": True},
        {"type": "TEXT", "name": "visitorId", "simpleValueType": True},
    ],
)
SNAPCHAT_TEMPLATE = parametered_template(
    92, "Snapchat", "luratic", "NCL6Z",
    [
        {"type": "TEXT", "name": "accountId", "simpleValueType": True,
         "valueValidators": [{"type": "NON_EMPTY"}]},
        {"type": "TEXT", "name": "eventName", "simpleValueType": True},
    ],
)
REDDIT_TEMPLATE = parametered_template(
    93, "Reddit Pixel", "reddit", "PBGZL",
    [
        {"type": "TEXT", "name": "id", "simpleValueType": True,
         "valueValidators": [{"type": "NON_EMPTY"}]},
        {"type": "TEXT", "name": "eventType", "simpleValueType": True},
        {"type": "TEXT", "name": "conversionId", "simpleValueType": True},
    ],
)
VENDOR_TEMPLATES = [CRITEO_TEMPLATE, SNAPCHAT_TEMPLATE, REDDIT_TEMPLATE]


def test_role_hints_come_from_the_template_not_a_guess():
    """Vendors disagree on every name; the template states its own contract."""
    def hints(template):
        return template_role_hints(
            parse_template_parameters(template["templateData"])["parameters"]
        )

    criteo = hints(CRITEO_TEMPLATE)
    assert criteo["declares_events"] is False, "a loader template declares no event"
    assert criteo["id_parameters"][0] == "partnerId"
    assert "visitorId" not in criteo["id_parameters"], "a visitor id is not an account id"

    snap = hints(SNAPCHAT_TEMPLATE)
    assert snap["event_parameters"] == ["eventName"]
    assert snap["id_parameters"][0] == "accountId"

    reddit = hints(REDDIT_TEMPLATE)
    assert reddit["event_parameters"] == ["eventType"]
    assert reddit["id_parameters"][0] == "id", "the required id comes first"
    assert "conversionId" in reddit["id_parameters"]


def test_loader_template_without_events_is_a_setup_tag():
    """Criteo's loader has no event parameter and no 'base' word in its name."""
    tags = [tag(82, "Criteo Loader - Official", "cvt_KT9RV",
                {"partnerType": "partnerId", "partnerId": "123456"})]
    found = _detect_media_platforms(tags, VENDOR_TEMPLATES)
    setup = found["criteo"]["setup_tags"]
    assert len(setup) == 1, f"expected a setup tag, got {found['criteo']}"
    assert setup[0]["account_id_value"] == "123456"


def test_event_parameter_name_unknown_to_the_registry_still_works():
    """Snapchat uses `eventName`; the registry guessed `eventType`."""
    tags = [tag(84, "Snapchat", "cvt_NCL6Z",
                {"accountId": "123456789", "eventName": "SHARE"})]
    found = _detect_media_platforms(tags, SNAPCHAT_TEMPLATE and VENDOR_TEMPLATES)
    assert [e["name"] for e in found["snapchat"]["event_tags"]] == ["Snapchat"]
    assert found["snapchat"]["setup_tags"] == []


def test_pageview_event_value_still_counts_as_the_base_tag():
    tags = [tag(85, "Snapchat", "cvt_NCL6Z",
                {"accountId": "1", "eventName": "PAGE_VIEW"})]
    found = _detect_media_platforms(tags, VENDOR_TEMPLATES)
    assert len(found["snapchat"]["setup_tags"]) == 1


def test_consent_initialization_is_detected_by_tag_not_by_trigger():
    """The Consent Initialization trigger is reserved and never listed.

    Looking for a trigger of type `consentInit` reported "missing" in every
    container, correctly configured ones included.
    """
    cmp_on_consent_init = {
        "tagId": "77", "name": "CMP", "type": "html", "paused": False,
        "firingTriggerId": ["2147479572"], "parameter": [],
    }
    cmp_on_all_pages = {
        "tagId": "77", "name": "CMP", "type": "html", "paused": False,
        "firingTriggerId": ["2147479553"], "parameter": [],
    }

    # No workspace trigger has type consentInit -- that is the normal case.
    assert evaluate_consent_initialization([cmp_on_consent_init], [])["status"] == "present"

    late = evaluate_consent_initialization([cmp_on_all_pages], [])
    assert late["status"] == "missing"
    assert "runs too late" in late["remedy"]

    assert evaluate_consent_initialization([], [])["status"] == "missing"


def test_paused_consent_tag_does_not_count():
    paused = {
        "tagId": "77", "name": "CMP", "type": "html", "paused": True,
        "firingTriggerId": ["2147479572"], "parameter": [],
    }
    assert evaluate_consent_initialization([paused], [])["status"] == "missing"


def test_unparseable_template_does_not_become_a_loader():
    """Declaring no parameters must not be read as "this is a base tag"."""
    broken = gallery_template(99, "Meta Pixel", "facebook", "5RM3Q", params=[])
    tags = [tag(9, "Meta Thing", "cvt_5RM3Q", {"pixelId": "123"})]
    meta = _detect_media_platforms(tags, [broken])["meta"]
    assert meta["setup_tags"] == [], "an unparseable template must not imply a loader"
    assert len(meta["unclassified"]) == 1


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
