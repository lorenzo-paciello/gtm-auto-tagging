"""The check that runs BEFORE a tag is written.

Two failures reported from real use drive this file:

1. A Meta base pixel was created for a pixel id already installed as Custom
   HTML. The agent warned -- **after** creating it. The order was backwards:
   the workspace was left dirty and the cleanup fell to the user.
2. A GA4 Event tag named `page_view` was created for a measurement id that
   already has a Google Tag. Nothing was reported at all, because no base-tag
   comparison can see it: the event tag initialises nothing, and the Google Tag
   is not an event tag. Yet a Google Tag sends `page_view` by itself, so the
   property now counts every page view twice.

3. The same page_view tag was then refused on a property where the user had
   just set `send_page_view` to false -- the one case where the event tag is
   the correct fix. The switch is not a top-level parameter: a Google Tag keeps
   it in `configSettingsTable` and a GA4 Configuration in `fieldsToSet`, both
   as rows of a nested table. Reading only the top level never saw it, and the
   test that was supposed to cover this invented a top-level parameter, so it
   passed while the real case failed. `settings_table` below builds the shape
   the API actually returns.

4. A Google Ads conversion with an existing id and label was created anyway,
   because its trigger differed and the identity comparison had been made
   trigger-aware. That downgrade is right for a GA4 event placed on a second
   interaction and wrong for a conversion action, which Google Ads cannot tell
   apart from its twin.
5. A GA4 page_view tag was created for a property whose Google Tag reaches it
   through a lookup table -- the base tag's account was `{{Variable}}` and
   never matched the literal id. The same table then produced the opposite
   error, reporting a conflict against event tags that send different events.
6. Two LinkedIn Insight tags were missing from the audit. `bzi` is one of GTM's
   own built-in vendor tag types: neither `cvt_` nor Custom HTML, so nothing in
   the template or snippet machinery saw it.

`update_tag` runs the same check, with one difference that matters: the tag
being edited is excluded from the comparison, or every edit would report the
tag as a duplicate of itself.

The gate has to catch both without blocking legitimate work -- a container
holds dozens of GA4 event tags sharing one measurement id, and refusing the
next one would make the tool unusable. That balance is what these tests pin
down: the last group is as important as the first.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gtm_agent.tools.gtm_creation_gate import collect_conflicts  # noqa: E402
from gtm_agent.tools.gtm_creation_gate import looks_like_an_identifier  # noqa: E402

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def settings_table(key: str, rows: dict[str, str], columns=("parameter", "parameterValue")):
    """A GTM settings table, in the shape the API actually returns.

    This is not decoration. The first version of these tests invented a
    top-level `sendPageView` parameter, passed happily, and hid a live bug: on
    a real Google Tag the switch lives in `configSettingsTable`, as rows of
    `{parameter, parameterValue}`. A test that models the wrong shape proves
    nothing about the right one.
    """
    name_key, value_key = columns
    return {
        "type": "list",
        "key": key,
        "list": [
            {
                "type": "map",
                "map": [
                    {"type": "template", "key": name_key, "value": name},
                    {"type": "template", "key": value_key, "value": value},
                ],
            }
            for name, value in rows.items()
        ],
    }


def tag(tag_id: int, name: str, tag_type: str, params: dict[str, str], **extra: Any):
    return {
        "tagId": str(tag_id),
        "name": name,
        "type": tag_type,
        "parameter": [{"key": k, "value": v} for k, v in params.items()]
        + list(extra.get("tables", [])),
        "firingTriggerId": extra.get("triggers", ["2147479553"]),
        "paused": extra.get("paused", False),
    }


def context(**overrides: Any) -> dict[str, Any]:
    base = {
        "platform_by_type": {"cvt_meta": "meta"},
        "template_hints": {
            "cvt_meta": {
                "id_parameters": ["pixelId"],
                "event_parameters": ["eventName"],
                "declares_events": True,
                "parameter_count": 2,
            }
        },
        "constants": {"CONST - Meta Pixel ID": "156914648903155"},
        "template_roles": {},
    }
    base.update(overrides)
    return base


def kinds(result: dict[str, Any]) -> set[str]:
    return {c["kind"] for c in result["blocking_conflicts"]}


# ===========================================================================
# 1. The reported Meta case: a pixel already installed as Custom HTML
# ===========================================================================
META_HTML = tag(
    327,
    "FB - Pageview - Pixel",
    "html",
    {"html": "<script>fbq('init','1560938438095658');fbq('track','PageView');</script>"},
)


def test_a_second_base_pixel_is_blocked_before_it_is_written():
    result = collect_conflicts(
        "html",
        {"html": "<script>fbq('init','1560938438095658');fbq('track','PageView');</script>"},
        "Meta - Pageview - new",
        [META_HTML],
        context(),
    )
    check(not result["clean"], "a duplicate base pixel must not come back clean")
    check(
        "initialisation" in kinds(result),
        f"expected an initialisation conflict, got {kinds(result)}",
    )
    check(
        result["blocking_conflicts"][0]["tags"][0]["tagId"] == "327",
        "the conflict must name the existing tag so the user can look at it",
    )


def test_the_same_pixel_from_a_template_is_caught_by_the_html_copy():
    """The comparison is by account, not by implementation.

    A pixel installed as Custom HTML and then added again from a community
    template is the commonest duplication there is -- a half-finished
    migration. Listing tags by type never surfaces it.
    """
    result = collect_conflicts(
        "cvt_meta",
        {"pixelId": "1560938438095658", "eventName": "PageView"},
        "Meta Pixel - Base",
        [META_HTML],
        context(template_roles={"__candidate__": "setup"}),
    )
    check(
        "initialisation" in kinds(result),
        "a template base tag must be compared with the hand-written copy",
    )


def test_a_constant_reference_resolves_to_the_same_account():
    """`fbq('init', '{{CONST - Meta Pixel ID}}')` is the same pixel."""
    existing = tag(
        400,
        "Meta - Base",
        "html",
        {"html": "<script>fbq('init','{{CONST - Meta Pixel ID}}');</script>"},
    )
    result = collect_conflicts(
        "html",
        {"html": "<script>fbq('init','156914648903155');fbq('track','PageView');</script>"},
        "Meta - Base - copy",
        [existing],
        context(),
    )
    check(
        "initialisation" in kinds(result),
        "a parameterised pixel and a literal one are the same account",
    )


# ===========================================================================
# 2. The reported GA4 case: a base tag already sends page_view
# ===========================================================================
GOOGLE_TAG = tag(506, "GA4 - Configuration", "googtag", {"tagId": "G-Y0WWB1BJPJ"})


def test_ga4_page_view_event_is_blocked_when_a_google_tag_exists():
    """The case that produced no warning at all."""
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [GOOGLE_TAG],
        context(),
    )
    check(not result["clean"], "a redundant page_view event tag must be blocked")
    check(
        "already_sent_by_a_base_tag" in kinds(result),
        f"expected already_sent_by_a_base_tag, got {kinds(result)}",
    )


def test_page_view_is_allowed_when_the_google_tag_has_it_disabled():
    """`send_page_view: false` is exactly when the event tag IS needed.

    Reported from real use: the user turned the switch off and was still told
    the new tag would double-count. The switch is not a top-level parameter --
    it is a row in `configSettingsTable` -- so reading only the top level never
    saw it.
    """
    quiet = tag(
        506,
        "GA4 - Configuration",
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ"},
        tables=[settings_table("configSettingsTable", {"send_page_view": "false"})],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [quiet],
        context(),
    )
    check(
        result["clean"],
        "with send_page_view disabled the event tag is the correct fix, not a "
        f"duplicate -- got {kinds(result)}",
    )


def test_page_view_is_allowed_when_a_ga4_configuration_disables_it():
    """The legacy GA4 Configuration keeps the same switch in `fieldsToSet`,
    with differently named columns."""
    quiet = tag(
        400,
        "GA4 - Configuration (legacy)",
        "gaawc",
        {"measurementId": "G-Y0WWB1BJPJ"},
        tables=[
            settings_table(
                "fieldsToSet",
                {"send_page_view": "false"},
                columns=("name", "value"),
            )
        ],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [quiet],
        context(),
    )
    check(
        result["clean"],
        f"the legacy configuration's switch must be read too, got {kinds(result)}",
    )


def test_page_view_is_still_blocked_when_the_switch_is_on():
    """The table exists and says true: the base tag does send the page view."""
    loud = tag(
        506,
        "GA4 - Configuration",
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ"},
        tables=[
            settings_table(
                "configSettingsTable",
                {"send_page_view": "true", "server_container_url": "https://x.example"},
            )
        ],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [loud],
        context(),
    )
    check(
        "already_sent_by_a_base_tag" in kinds(result),
        "an explicit true must not be mistaken for a disabled switch",
    )


def test_an_unresolvable_switch_falls_back_to_the_default():
    """`{{Some Variable}}` cannot be read. GTM's default is on, so assume on.

    Guessing "off" would let a genuine double-count through, which is the
    failure that costs the user data rather than a question.
    """
    unknown = tag(
        506,
        "GA4 - Configuration",
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ"},
        tables=[
            settings_table(
                "configSettingsTable", {"send_page_view": "{{Lookup - Send PV}}"}
            )
        ],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [unknown],
        context(),
    )
    check(
        "already_sent_by_a_base_tag" in kinds(result),
        "an unreadable switch must fall back to GTM's default, which is on",
    )


def test_a_constant_can_disable_the_switch():
    """A settings value that is a constant reference resolves like any other."""
    quiet = tag(
        506,
        "GA4 - Configuration",
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ"},
        tables=[
            settings_table("configSettingsTable", {"send_page_view": "{{CONST - Send PV}}"})
        ],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [quiet],
        context(
            constants={
                "CONST - Meta Pixel ID": "156914648903155",
                "CONST - Send PV": "false",
            }
        ),
    )
    check(
        result["clean"],
        f"a constant holding false must disable the switch, got {kinds(result)}",
    )


def test_an_identifier_inside_a_settings_row_is_found():
    """Configuration is not only top-level parameters."""
    existing = tag(
        700,
        "Floodlight - Counter",
        "flc",
        {"groupTag": "sale"},
        tables=[
            settings_table(
                "customVariable", {"advertiserId": "13520834"}, columns=("key", "value")
            )
        ],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "13520834", "eventName": "test"},
        "probe",
        [existing],
        context(),
    )
    check(
        any(a["kind"] == "same_identifier" for a in result["advisory"]),
        "an id held in a nested settings row must still be searchable",
    )


def test_a_different_property_is_not_a_conflict():
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-DIFFERENT01", "eventName": "page_view"},
        "GA4 - Event - page_view",
        [GOOGLE_TAG],
        context(),
    )
    check(result["clean"], "another property's page view is unrelated")


def test_a_media_base_tag_already_sends_its_page_view():
    """fbq('init') fires PageView on load; a separate PageView tag repeats it."""
    result = collect_conflicts(
        "html",
        {"html": "<script>fbq('track','PageView');</script>"},
        "Meta - PageView event",
        [META_HTML],
        context(),
    )
    check(
        "already_sent_by_a_base_tag" in kinds(result),
        f"expected the base pixel's own page view to be recognised, got {kinds(result)}",
    )


# ===========================================================================
# 3. Identical configuration, and identical script
# ===========================================================================
def test_an_identical_event_tag_is_blocked():
    existing = tag(
        535,
        "GA4 - Event - purchase",
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "purchase"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "purchase"},
        "GA4 - Purchase (new)",
        [existing],
        context(),
    )
    check(
        "identical_configuration" in kinds(result),
        f"an identical event tag must be blocked, got {kinds(result)}",
    )


def test_renaming_does_not_get_past_the_gate():
    """The comparison is by configuration. A new name is not a new tag."""
    existing = tag(
        535,
        "GA4 - Event - purchase",
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "purchase"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "purchase"},
        "Something Completely Different",
        [existing],
        context(),
    )
    check(not result["clean"], "renaming must not bypass the check")


def test_an_identical_script_for_an_unknown_vendor_is_blocked():
    """No registry names this vendor; the script is still the same script."""
    script = (
        "<script>(function(w,d){var s=d.createElement('script');"
        "s.src='https://cdn.obscure-vendor.example/pixel.js?acct=99887766';"
        "s.async=true;d.head.appendChild(s);w.obscureQueue=w.obscureQueue||[];"
        "w.obscureQueue.push(['page']);})(window,document);</script>"
    )
    existing = tag(700, "Obscure vendor", "html", {"html": script})
    result = collect_conflicts(
        "html",
        {"html": script.replace("\n", " ").replace("  ", " ")},
        "Obscure vendor (copy)",
        [existing],
        context(),
    )
    check(
        "identical_script" in kinds(result),
        f"an unregistered vendor's duplicated script must be caught, got {kinds(result)}",
    )


# ===========================================================================
# 4. What must NOT be blocked -- the noise this design has to avoid
# ===========================================================================
def test_a_new_event_on_an_existing_property_is_allowed():
    """One measurement id belongs in every GA4 event tag for that property."""
    existing = [
        tag(
            i,
            f"GA4 - Event - click_{i}",
            "gaawe",
            {"measurementId": "G-Y0WWB1BJPJ", "eventName": f"click_{i}"},
        )
        for i in range(20)
    ]
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "scroll_75"},
        "GA4 - Event - scroll_75",
        existing + [GOOGLE_TAG],
        context(),
    )
    check(
        result["clean"],
        f"a new event name must not be blocked, got {kinds(result)}",
    )
    check(
        result["advisory"] and result["advisory"][0]["kind"] == "same_identifier",
        "the shared measurement id should still be reported as context",
    )


def test_an_event_name_that_looks_like_an_id_is_still_an_event():
    """`scroll_75` has the shape of an identifier. The parameter name decides.

    Reading it as an identifier made two unrelated scroll tags compare as
    identically configured.
    """
    existing = tag(
        1,
        "GA4 - Event - scroll_50",
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "scroll_50"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "scroll_75"},
        "GA4 - Event - scroll_75",
        [existing],
        context(),
    )
    check(
        result["clean"],
        f"scroll_75 and scroll_50 are different events, got {kinds(result)}",
    )
    check(
        result["events_in_payload"] == ["scroll_75"],
        f"scroll_75 should be read as an event, got {result['events_in_payload']}",
    )


def test_a_media_event_tag_does_not_duplicate_a_base_tag():
    """An event call carries no account, so it cannot duplicate a pixel."""
    result = collect_conflicts(
        "html",
        {"html": "<script>fbq('track','Purchase',{value:10});</script>"},
        "Meta - Purchase",
        [META_HTML],
        context(),
    )
    check(
        "initialisation" not in kinds(result),
        "an event tag must not be reported as a duplicate base pixel",
    )


def test_an_empty_workspace_blocks_nothing():
    result = collect_conflicts(
        "googtag", {"tagId": "G-NEW123456"}, "Google Tag", [], context()
    )
    check(result["clean"], "nothing exists, so nothing can be duplicated")
    check(
        "Proceed" in result["next_step"],
        "a clean result should say so plainly",
    )


def test_a_paused_duplicate_is_still_reported():
    """A paused tag can be unpaused. It is still a duplicate to resolve."""
    paused = tag(
        327,
        "FB - Pageview (paused)",
        "html",
        {"html": "<script>fbq('init','1560938438095658');</script>"},
        paused=True,
    )
    result = collect_conflicts(
        "html",
        {"html": "<script>fbq('init','1560938438095658');</script>"},
        "Meta - Base",
        [paused],
        context(),
    )
    check(not result["clean"], "a paused duplicate should still be surfaced")


# ===========================================================================
# 5. The registry-free identifier test
# ===========================================================================
def test_identifier_shapes():
    for value in (
        "G-Y0WWB1BJPJ",
        "AW-16474873505",
        "DC-13520834",
        "1560938438095658",
        "C4A1B2C3D4E5F6G7H8I9",
        "5jhECLbxvaIZEKG96q89",
        "t2_abc123",
        "{{CONST - Pixel ID}}",
    ):
        check(looks_like_an_identifier(value), f"{value!r} should read as an identifier")

    for value in (
        "purchase",
        "page_view",
        "true",
        "12",
        "",
        "https://example.com/path",
        "Some tag name here",
    ):
        check(
            not looks_like_an_identifier(value),
            f"{value!r} should NOT read as an identifier",
        )


def test_next_step_tells_the_agent_to_ask_first():
    result = collect_conflicts(
        "googtag", {"tagId": "G-Y0WWB1BJPJ"}, "Google Tag", [GOOGLE_TAG], context()
    )
    check(not result["clean"], "an existing destination must block")
    step = result["next_step"]
    check("ASK" in step, "the next step must be to ask the user")
    check(
        "confirm_duplicate=true" in step,
        "the next step must name the flag that records the user's decision",
    )
    check(
        "own judgement" in step,
        "the agent must be told not to set that flag by itself",
    )


# ===========================================================================
# 6. The same gate on update_tag -- where a tag must not conflict with itself
# ===========================================================================
def test_editing_a_tag_does_not_conflict_with_itself():
    """The commonest update is a no-op on identity: a rename, a new trigger."""
    existing = tag(506, "GA4 - Configuration", "googtag", {"tagId": "G-Y0WWB1BJPJ"})
    result = collect_conflicts(
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ"},
        "GA4 - Configuration (renamed)",
        [existing],
        context(),
        exclude_tag_id="506",
    )
    check(
        result["clean"],
        f"a tag must not be reported as a duplicate of itself, got {kinds(result)}",
    )


def test_pointing_a_tag_at_an_account_another_tag_owns_is_blocked():
    """Duplication by the quieter route: no tag is created, yet now there are two."""
    edited = tag(600, "Google Tag - staging", "googtag", {"tagId": "G-STAGING01"})
    other = tag(506, "GA4 - Configuration", "googtag", {"tagId": "G-Y0WWB1BJPJ"})
    result = collect_conflicts(
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ"},
        "Google Tag - staging",
        [edited, other],
        context(),
        exclude_tag_id="600",
    )
    check(
        "initialisation" in kinds(result),
        f"repointing a tag at an occupied destination must block, got {kinds(result)}",
    )
    check(
        [t["tagId"] for c in result["blocking_conflicts"] for t in c["tags"]] == ["506"],
        "the conflict must name the other tag, not the one being edited",
    )


def test_editing_an_event_tag_into_an_existing_one_is_blocked():
    edited = tag(
        1,
        "GA4 - Event - scroll",
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "scroll"},
    )
    twin = tag(
        2,
        "GA4 - Event - purchase",
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "purchase"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "purchase"},
        "GA4 - Event - scroll",
        [edited, twin],
        context(),
        exclude_tag_id="1",
    )
    check(
        "identical_configuration" in kinds(result),
        f"editing a tag into a copy of another must block, got {kinds(result)}",
    )


# ===========================================================================
# 7. Google Ads and Floodlight: the parameters that define the tag
# ===========================================================================
def advisory_kinds(result):
    return {a["kind"] for a in result["advisory"]}


LINKER = tag(9, "Conversion Linker", "gclidw", {"enableCrossDomain": "false"})
ADS_BASE = tag(10, "Google Tag - Ads", "googtag", {"tagId": "AW-16474873505"})


def test_a_different_floodlight_activity_is_not_a_duplicate():
    """The bug this rule was rewritten for.

    `groupTag` (`sale`) and `activityTag` (`purch0`) are short words with no
    digits, so an identity built from values that merely LOOK like ids ignored
    both -- and every new activity on an advertiser compared identical to every
    other one. The check would have blocked every Floodlight tag a user ever
    created.
    """
    existing = tag(
        1,
        "FL - Purchase",
        "flc",
        {"advertiserId": "13520834", "groupTag": "sale", "activityTag": "purch0"},
    )
    result = collect_conflicts(
        "flc",
        {"advertiserId": "13520834", "groupTag": "lead", "activityTag": "signu0"},
        "FL - Lead",
        [existing, LINKER],
        context(),
    )
    check(
        result["clean"],
        f"a different activity on one advertiser must be allowed, got {kinds(result)}",
    )


def test_the_same_floodlight_activity_is_a_duplicate():
    existing = tag(
        1,
        "FL - Purchase",
        "flc",
        {"advertiserId": "13520834", "groupTag": "sale", "activityTag": "purch0"},
    )
    result = collect_conflicts(
        "flc",
        {"advertiserId": "13520834", "groupTag": "sale", "activityTag": "purch0"},
        "FL - Purchase (copy)",
        [existing, LINKER],
        context(),
    )
    check(not result["clean"], "the same activity twice must be blocked")


def test_google_ads_compares_id_and_label():
    existing = tag(
        1,
        "Ads - Purchase",
        "awct",
        {"conversionId": "16474873505", "conversionLabel": "5jhECLbxvaIZEKG96q89"},
    )
    same = collect_conflicts(
        "awct",
        {"conversionId": "16474873505", "conversionLabel": "5jhECLbxvaIZEKG96q89"},
        "Ads - Purchase (copy)",
        [existing, LINKER, ADS_BASE],
        context(),
    )
    check(not same["clean"], "the same conversion id AND label must be blocked")

    other = collect_conflicts(
        "awct",
        {"conversionId": "16474873505", "conversionLabel": "DIFFERENTlabel123456"},
        "Ads - Lead",
        [existing, LINKER, ADS_BASE],
        context(),
    )
    check(
        other["clean"],
        f"a different label is a different conversion, got {kinds(other)}",
    )


def test_a_hand_written_google_ads_conversion_is_compared_with_the_native_one():
    """`gtag('event','conversion',{send_to:'AW-.../label'})` is the same tag."""
    manual = tag(
        1,
        "Ads conversion (legacy HTML)",
        "html",
        {
            "html": "<script>gtag('event','conversion',"
            "{'send_to':'AW-16474873505/5jhECLbxvaIZEKG96q89'});</script>"
        },
    )
    result = collect_conflicts(
        "awct",
        {"conversionId": "16474873505", "conversionLabel": "5jhECLbxvaIZEKG96q89"},
        "Ads - Purchase",
        [manual, LINKER, ADS_BASE],
        context(),
    )
    check(
        "duplicate_conversion" in kinds(result),
        f"a hand-written conversion must be found, got {kinds(result)}",
    )


def test_a_floodlight_counter_pasted_as_html_is_compared_with_the_native_tag():
    manual = tag(
        1,
        "FL counter (iframe)",
        "html",
        {
            "html": '<iframe src="https://13520834.fls.doubleclick.net/'
            'activityi;src=13520834;type=sale;cat=purch0;dc_lat=;"></iframe>'
        },
    )
    result = collect_conflicts(
        "flc",
        {"advertiserId": "13520834", "groupTag": "sale", "activityTag": "purch0"},
        "FL - Purchase",
        [manual, LINKER],
        context(),
    )
    check(
        "duplicate_conversion" in kinds(result),
        f"a pasted Floodlight counter must be found, got {kinds(result)}",
    )


def test_only_one_conversion_linker_belongs_in_a_container():
    result = collect_conflicts(
        "gclidw", {"enableCrossDomain": "false"}, "Conversion Linker 2", [LINKER], context()
    )
    check(not result["clean"], "a second Conversion Linker must be blocked")


# ===========================================================================
# 8. Google's own products written by hand
# ===========================================================================
def test_a_manual_gtag_install_conflicts_with_a_google_tag():
    """A container migrating into GTM carries gtag.js as Custom HTML for months."""
    manual = tag(
        1,
        "GA4 - gtag.js (legacy)",
        "html",
        {
            "html": "<script async src='https://www.googletagmanager.com/gtag/js"
            "?id=G-Y0WWB1BJPJ'></script><script>gtag('config','G-Y0WWB1BJPJ');</script>"
        },
    )
    result = collect_conflicts(
        "googtag", {"tagId": "G-Y0WWB1BJPJ"}, "Google Tag", [manual], context()
    )
    check(
        "initialisation" in kinds(result),
        f"a hand-written gtag config configures the same destination, got {kinds(result)}",
    )


def test_the_reverse_direction_holds_too():
    result = collect_conflicts(
        "html",
        {"html": "<script>gtag('config','G-Y0WWB1BJPJ');</script>"},
        "GA4 by hand",
        [GOOGLE_TAG],
        context(),
    )
    check(
        "initialisation" in kinds(result),
        f"adding gtag by hand where a Google Tag exists must block, got {kinds(result)}",
    )


# ===========================================================================
# 9. Variables that are not one value
# ===========================================================================
LOOKUP_CONTEXT = dict(
    platform_by_type={},
    template_hints={},
    constants={},
    template_roles={},
    variable_candidates={
        "[ED]ID-Metrica-Estados": {"G-ZXLCXNRE56", "G-EH76BC8Q2E", "G-S8SSRCG80T"}
    },
)


def test_a_lookup_table_can_already_cover_the_property():
    """One Google Tag behind a RegEx table covers every id the table lists."""
    routed = tag(
        1, "Google Tag - states", "googtag", {"tagId": "{{[ED]ID-Metrica-Estados}}"}
    )
    result = collect_conflicts(
        "googtag",
        {"tagId": "G-ZXLCXNRE56"},
        "Google Tag - AC",
        [routed],
        LOOKUP_CONTEXT,
    )
    check(
        "possible_duplicate_via_variable" in kinds(result),
        f"a lookup output must be recognised, got {kinds(result)}",
    )


def test_an_event_tag_behind_the_lookup_does_not_duplicate_a_base_tag():
    """Routing to a destination is not configuring it.

    Live, creating one Google Tag reported four "duplicates": the Google Tag
    behind the table, and three GA4 event tags routing through the same table.
    The event tags send TO the destination; only the Google Tag configures it.
    """
    routed_event = tag(
        2,
        "GA4 - Event - states",
        "gaawe",
        {"measurementId": "{{[ED]ID-Metrica-Estados}}", "eventName": "scroll"},
    )
    result = collect_conflicts(
        "googtag",
        {"tagId": "G-ZXLCXNRE56"},
        "Google Tag - AC",
        [routed_event],
        LOOKUP_CONTEXT,
    )
    check(
        result["clean"],
        f"an event tag is not a configuration tag, got {kinds(result)}",
    )


def test_an_id_the_lookup_cannot_produce_is_clean():
    routed = tag(
        1, "Google Tag - states", "googtag", {"tagId": "{{[ED]ID-Metrica-Estados}}"}
    )
    result = collect_conflicts(
        "googtag",
        {"tagId": "G-NOTINTHETABLE"},
        "Google Tag - other",
        [routed],
        LOOKUP_CONTEXT,
    )
    check(result["clean"], f"an unrelated property must stay clean, got {kinds(result)}")


# ===========================================================================
# 10. Foundations, and preferring a template
# ===========================================================================
def test_a_missing_conversion_linker_is_reported_without_blocking():
    result = collect_conflicts(
        "awct",
        {"conversionId": "16474873505", "conversionLabel": "abcDEF123456"},
        "Ads - Purchase",
        [ADS_BASE],
        context(),
    )
    check(
        "missing_prerequisite" in advisory_kinds(result),
        f"a missing Conversion Linker must be reported, got {advisory_kinds(result)}",
    )
    check(
        result["clean"],
        "a missing prerequisite is a warning, not a duplicate -- it must not block",
    )


def test_a_present_conversion_linker_is_not_reported():
    result = collect_conflicts(
        "awct",
        {"conversionId": "16474873505", "conversionLabel": "abcDEF123456"},
        "Ads - Purchase",
        [LINKER, ADS_BASE],
        context(),
    )
    check(
        "missing_prerequisite" not in advisory_kinds(result),
        "nothing is missing, so nothing should be reported",
    )


def test_custom_html_is_flagged_when_a_template_is_installed():
    result = collect_conflicts(
        "html",
        {"html": "<script>fbq('init','999888777666555');</script>"},
        "Meta - Base by hand",
        [],
        context(),
    )
    check(
        "prefer_template" in advisory_kinds(result),
        f"an installed template should be preferred, got {advisory_kinds(result)}",
    )
    check(result["clean"], "preferring a template is advice, not a block")


# ===========================================================================
# 11. The same event for the same account
# ===========================================================================
META_TEMPLATE_BASE = tag(
    20, "Meta - Base", "cvt_meta", {"pixelId": "999888777666555", "eventName": "PageView"}
)


def test_the_same_media_event_on_the_same_trigger_is_blocked():
    existing = tag(
        21,
        "Meta - Purchase",
        "cvt_meta",
        {"pixelId": "999888777666555", "eventName": "Purchase"},
        triggers=["55"],
    )
    result = collect_conflicts(
        "cvt_meta",
        {"pixelId": "999888777666555", "eventName": "Purchase"},
        "Meta - Purchase (again)",
        [existing],
        context(),
        firing_trigger_ids=["55"],
    )
    check(not result["clean"], "the same event on the same trigger must be blocked")


def test_an_identical_tag_on_a_different_trigger_only_asks():
    """A second placement of the same measurement is normal.

    Two GA4 `select_item` tags on different lists, or one Meta Purchase on the
    web flow and another on a separate one, are identical by configuration and
    entirely legitimate. Blocking those would teach the user to pass
    confirm_duplicate without reading, which is worse than not checking.
    """
    existing = tag(
        21,
        "Meta - Purchase (web)",
        "cvt_meta",
        {"pixelId": "999888777666555", "eventName": "Purchase"},
        triggers=["55"],
    )
    result = collect_conflicts(
        "cvt_meta",
        {"pixelId": "999888777666555", "eventName": "Purchase"},
        "Meta - Purchase (app)",
        [existing],
        context(),
        firing_trigger_ids=["77"],
    )
    check(result["clean"], f"a different trigger must not block, got {kinds(result)}")
    check(
        any("21" == t["tagId"] for a in result["advisory"] for t in a["tags"]),
        "the existing tag must still be named, so the user can judge",
    )


def test_the_same_event_for_one_account_is_caught_even_when_parameters_differ():
    """Identity is platform + account + event, not byte equality.

    Two Meta Purchase tags for one pixel on one trigger are a double-count
    however differently their optional parameters are filled in.
    """
    existing = tag(
        21,
        "Meta - Purchase",
        "cvt_meta",
        {
            "pixelId": "999888777666555",
            "eventName": "Purchase",
            "objectPropertyList": "value",
        },
        triggers=["55"],
    )
    result = collect_conflicts(
        "cvt_meta",
        {"pixelId": "999888777666555", "eventName": "Purchase"},
        "Meta - Purchase (again)",
        [existing],
        context(),
        firing_trigger_ids=["55"],
    )
    check(
        "duplicate_event_for_account" in kinds(result),
        f"the same event for one account must be caught, got {kinds(result)}",
    )


def test_a_different_pixel_of_the_same_platform_is_not_a_duplicate():
    existing = tag(
        21,
        "Meta - Purchase - brand A",
        "cvt_meta",
        {"pixelId": "111111111111111", "eventName": "Purchase"},
        triggers=["55"],
    )
    result = collect_conflicts(
        "cvt_meta",
        {"pixelId": "999888777666555", "eventName": "Purchase"},
        "Meta - Purchase - brand B",
        [existing],
        context(),
        firing_trigger_ids=["55"],
    )
    check(
        "duplicate_event_for_account" not in kinds(result),
        f"two ad accounts are two businesses, got {kinds(result)}",
    )


# ===========================================================================
# 12. Four failures found by testing against a real container
# ===========================================================================
def test_a_built_in_vendor_tag_type_is_a_base_tag():
    """GTM ships its own tag types for some vendors, and they were invisible.

    LinkedIn Insight is `bzi`, a built-in type -- neither `cvt_` nor Custom
    HTML, so nothing in the gallery-marker or snippet machinery saw it. The
    audit listed a container's two hand-written LinkedIn pixels and silently
    skipped its two native ones, which reads as the model having missed them.
    Its only parameter is `id`.
    """
    existing = tag(83, "Pixel_Linkedin_Acredita", "bzi", {"id": "7101604"})
    result = collect_conflicts(
        "bzi", {"id": "7101604"}, "LinkedIn Insight", [existing], context()
    )
    check(
        "initialisation" in kinds(result),
        f"a built-in vendor tag must count as a base tag, got {kinds(result)}",
    )


def test_a_built_in_vendor_tag_compares_with_the_hand_written_copy():
    """The same partner id, one native and one pasted, is one pixel twice."""
    manual = tag(
        307,
        "LinkedIn - Pageview",
        "html",
        {"html": '<script>_linkedin_partner_id = "7101604";</script>'},
    )
    result = collect_conflicts(
        "bzi", {"id": "7101604"}, "LinkedIn Insight", [manual], context()
    )
    check(
        "initialisation" in kinds(result),
        f"native and hand-written must compare, got {kinds(result)}",
    )


def test_a_different_partner_id_is_not_a_duplicate():
    existing = tag(83, "LinkedIn A", "bzi", {"id": "7101604"})
    result = collect_conflicts(
        "bzi", {"id": "5192844"}, "LinkedIn B", [existing], context()
    )
    check(result["clean"], f"two partner ids are two accounts, got {kinds(result)}")


ROUTED_CONTEXT = dict(
    platform_by_type={},
    template_hints={},
    constants={},
    template_roles={},
    variable_candidates={"[ED]ID-Metrica-Estados": {"G-STE61FKTJH", "G-ZXLCXNRE56"}},
)


def routed_google_tag(send_page_view=None):
    tables = (
        [settings_table("configSettingsTable", {"send_page_view": send_page_view})]
        if send_page_view is not None
        else []
    )
    return tag(
        34,
        "[ED] Tag - Estados",
        "googtag",
        {"tagId": "{{[ED]ID-Metrica-Estados}}"},
        tables=tables,
    )


def test_a_base_tag_routed_by_lookup_still_sends_the_page_view():
    """Reported live: the page_view tag was created with no conflict at all.

    The Google Tag's destination is a lookup table, so its account never
    matched the literal id being requested, and the rule that should have
    stopped it never fired.
    """
    for switch in (None, "true"):
        result = collect_conflicts(
            "gaawe",
            {"measurementId": "G-STE61FKTJH", "eventName": "page_view"},
            "GA4 - page_view",
            [routed_google_tag(switch)],
            ROUTED_CONTEXT,
        )
        check(
            "already_sent_by_a_base_tag" in kinds(result),
            f"send_page_view={switch!r} means the page view is sent -- got {kinds(result)}",
        )


def test_a_routed_base_tag_with_the_switch_off_allows_the_page_view_tag():
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-STE61FKTJH", "eventName": "page_view"},
        "GA4 - page_view",
        [routed_google_tag("false")],
        ROUTED_CONTEXT,
    )
    check(
        "already_sent_by_a_base_tag" not in kinds(result),
        f"with the switch off the event tag is the fix, got {kinds(result)}",
    )


def test_a_lookup_conflict_must_agree_on_the_whole_identity():
    """Reported live: a conflict was raised for a different measurement id.

    A lookup supplies one field. For `gaawe` that is `measurementId`, and
    `eventName` still has to match -- otherwise a page_view tag reports a
    conflict with every event tag routed through the same table, whatever
    event each one actually sends.
    """
    other_event = tag(
        152,
        "GA4 - Evento - Coleta",
        "gaawe",
        {"measurementId": "{{[ED]ID-Metrica-Estados}}", "eventName": "coleta"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-STE61FKTJH", "eventName": "page_view"},
        "GA4 - page_view",
        [other_event],
        ROUTED_CONTEXT,
    )
    check(
        "possible_duplicate_via_variable" not in kinds(result),
        f"a different event is not a duplicate, got {kinds(result)}",
    )


def test_the_same_event_routed_through_the_lookup_is_a_conflict():
    twin = tag(
        152,
        "GA4 - page_view - Estados",
        "gaawe",
        {"measurementId": "{{[ED]ID-Metrica-Estados}}", "eventName": "page_view"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-STE61FKTJH", "eventName": "page_view"},
        "GA4 - page_view - AC",
        [twin],
        ROUTED_CONTEXT,
    )
    check(
        "possible_duplicate_via_variable" in kinds(result),
        f"the same event through the same table must be raised, got {kinds(result)}",
    )


def test_a_duplicate_conversion_blocks_on_any_trigger():
    """Reported live: the duplicate was created because its trigger differed.

    A second GA4 `select_item` on a different list is ordinary work. A second
    Google Ads conversion with the same id and label is the same conversion
    action counted twice, and Google Ads cannot tell the two tags apart.
    """
    existing = tag(
        54,
        "Ads - Amplifica",
        "awct",
        {"conversionId": "796268201", "conversionLabel": "gLHaCMbrsJIBEKmt2PsC"},
        triggers=["11"],
    )
    result = collect_conflicts(
        "awct",
        {"conversionId": "796268201", "conversionLabel": "gLHaCMbrsJIBEKmt2PsC"},
        "Ads - Amplifica (copy)",
        [existing, LINKER, ADS_BASE],
        context(),
        firing_trigger_ids=["99"],
    )
    check(
        not result["clean"],
        f"a duplicate conversion must block whatever it fires on, got {kinds(result)}",
    )


def test_a_floodlight_duplicate_also_blocks_on_any_trigger():
    existing = tag(
        1,
        "FL - Purchase",
        "flc",
        {"advertiserId": "13520834", "groupTag": "sale", "activityTag": "purch0"},
        triggers=["11"],
    )
    result = collect_conflicts(
        "flc",
        {"advertiserId": "13520834", "groupTag": "sale", "activityTag": "purch0"},
        "FL - Purchase (copy)",
        [existing, LINKER],
        context(),
        firing_trigger_ids=["99"],
    )
    check(not result["clean"], "the same activity twice must block on any trigger")


def test_a_ga4_event_on_a_different_trigger_still_only_asks():
    """The downgrade survives where it belongs: a second placement of an event."""
    existing = tag(
        1,
        "GA4 - select_item - list A",
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "select_item"},
        triggers=["11"],
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "select_item"},
        "GA4 - select_item - list B",
        [existing],
        context(),
        firing_trigger_ids=["99"],
    )
    check(
        result["clean"],
        f"a second placement of a GA4 event must not block, got {kinds(result)}",
    )


# ===========================================================================
# 13. Working in containers this project has never seen
# ===========================================================================
def test_a_vendor_tag_type_nobody_named_is_still_a_base_tag():
    """No hardcoded list of built-in types is ever complete.

    GTM ships built-in tag types for vendors that come and go, and this project
    has to work in containers it has never seen. The rule is structural rather
    than enumerated: not Google's own, not a template, not script. Such a tag
    is compared with others of its own type and appears in the inventory. Only
    the vendor's NAME is missing, and no comparison needs it.
    """
    existing = tag(
        1, "Some vendor", "vendor_type_from_2027", {"accountKey": "ABC12345XYZ"}
    )
    result = collect_conflicts(
        "vendor_type_from_2027",
        {"accountKey": "ABC12345XYZ"},
        "Some vendor (copy)",
        [existing],
        context(),
    )
    check(
        "initialisation" in kinds(result),
        f"an unnamed vendor type must still compare, got {kinds(result)}",
    )


def test_two_accounts_of_an_unnamed_vendor_are_not_duplicates():
    existing = tag(
        1, "Some vendor A", "vendor_type_from_2027", {"accountKey": "ABC12345XYZ"}
    )
    result = collect_conflicts(
        "vendor_type_from_2027",
        {"accountKey": "ZZZ99999QQQ"},
        "Some vendor B",
        [existing],
        context(),
    )
    check(result["clean"], f"two accounts are two accounts, got {kinds(result)}")


def test_a_setting_held_in_a_variable_is_read():
    """Settings can live one indirection away from the tag.

    A governed container keeps a Google Tag's configuration in a `gtcs`
    variable so twenty tags share it. Reading only the tag's own table sees an
    empty configuration and concludes `send_page_view` is absent -- the same
    failure as before, one level further out.
    """
    routed = tag(
        34,
        "Google Tag",
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ", "configSettingsVariable": "{{Shared config}}"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - page_view",
        [routed],
        context(settings_variables={"Shared config": {"send_page_view": "false"}}),
    )
    check(
        result["clean"],
        f"the switch lives in the variable and says false, got {kinds(result)}",
    )


def test_a_settings_variable_that_leaves_the_switch_on_still_blocks():
    routed = tag(
        34,
        "Google Tag",
        "googtag",
        {"tagId": "G-Y0WWB1BJPJ", "configSettingsVariable": "{{Shared config}}"},
    )
    result = collect_conflicts(
        "gaawe",
        {"measurementId": "G-Y0WWB1BJPJ", "eventName": "page_view"},
        "GA4 - page_view",
        [routed],
        context(settings_variables={"Shared config": {"server_container_url": "https://x"}}),
    )
    check(
        "already_sent_by_a_base_tag" in kinds(result),
        f"nothing turned it off, so the page view is sent, got {kinds(result)}",
    )


for name, function in sorted(list(globals().items())):
    if name.startswith("test_") and callable(function):
        try:
            function()
            print(f"PASS  {name}")
        except Exception as error:  # noqa: BLE001
            failures.append(f"{name}: {error!r}")
            print(f"ERROR {name}: {error!r}")

print(f"\n{len(failures)} failure(s)")
for failure in failures:
    print("  -", failure)
sys.exit(1 if failures else 0)
