"""Guard duplicate detection.

Duplication is a question about BASE tags. On most platforms the account id
appears only in the initialisation call, and event tags use whichever library
that call loaded:

    fbq('init', '123')            <- the account lives here
    fbq('track', 'AddToCart')     <- no account; uses the pixel above

Comparing every tag by `(account, event)` produced noise rather than findings:
in a real 180-tag container it reported ten groups, of which seven were
legitimate repeats -- twenty GA4 tags firing `click` on twenty pages, seven Meta
`Lead` tags on seven campaigns. Restricting the comparison to initialisations
left three groups, all real.

Runs with pytest, or standalone: `python tests/test_tag_identity.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gtm_agent.tools.gtm_duplicates import collect_findings  # noqa: E402
from gtm_agent.tools.tag_identity import (  # noqa: E402
    conversion_config_of,
    describe_base_overlap,
    event_only_platforms,
    html_fingerprint,
    initialisations_of,
)
from gtm_agent.tools.media_platforms import MEDIA_PLATFORMS  # noqa: E402
from gtm_agent.tools.vendor_snippets import (  # noqa: E402
    find_event_only_platforms,
    find_initialisations,
    script_fingerprint,
)

META_TYPE = "cvt_5RM3Q"
CONTEXT = {
    "platform_by_type": {META_TYPE: "meta"},
    "template_hints": {
        META_TYPE: {
            "id_parameters": ["pixelId"],
            "event_parameters": ["eventName", "standardEventName"],
            "declares_events": True,
            "parameter_count": 8,
        }
    },
    "constants": {"CONST - Meta Pixel": "1560938438095658"},
    "template_roles": {},
}


def tag(tag_id, name, tag_type, params, triggers=("2147479553",), paused=False):
    return {
        "tagId": str(tag_id),
        "name": name,
        "type": tag_type,
        "paused": paused,
        "firingTriggerId": list(triggers),
        "parameter": [
            {"type": "template", "key": k, "value": str(v)} for k, v in params.items()
        ],
    }


def with_roles(**roles):
    context = dict(CONTEXT)
    context["template_roles"] = {str(k): v for k, v in roles.items()}
    return context


# ---------------------------------------------------------------------------
# Only initialisations count
# ---------------------------------------------------------------------------


def test_an_event_snippet_initialises_nothing():
    """The core rule: `fbq('track', ...)` configures no account."""
    assert find_initialisations("fbq('track','AddToCart');") == []
    assert find_event_only_platforms("fbq('track','AddToCart');") == ["meta"]

    event_tag = tag(1, "Meta AddToCart", "html", {"html": "fbq('track','AddToCart');"})
    assert initialisations_of(event_tag, **CONTEXT) == []
    assert event_only_platforms(event_tag) == ["meta"]


def test_an_init_snippet_yields_the_account():
    found = initialisations_of(
        tag(1, "Meta base", "html", {"html": "fbq('init','1560938438095658');"}),
        **CONTEXT,
    )
    assert [(i.product, i.account, i.implementation) for i in found] == [
        ("meta", "1560938438095658", "html")
    ]


def test_a_template_event_tag_does_not_initialise():
    """Only a template tag in the SETUP role configures its pixel."""
    event_tag = tag(
        14, "Meta Conv Lead", META_TYPE,
        {"pixelId": "1006413604534931", "standardEventName": "Lead"},
    )
    assert initialisations_of(event_tag, **with_roles(**{"14": "event"})) == []
    assert len(initialisations_of(event_tag, **with_roles(**{"14": "setup"}))) == 1


def test_repeated_ga4_events_are_not_a_finding():
    """Twenty tags firing `click` on twenty pages are twenty legitimate tags."""
    tags = [
        tag(i, f"GA4 click {i}", "gaawe",
            {"eventName": "click", "measurementIdOverride": "G-1"}, (str(i),))
        for i in range(1, 21)
    ]
    result = collect_findings(tags, CONTEXT)
    assert result["clean"], result["groups"]


def test_html_and_template_base_tags_collide():
    """The same pixel installed twice, two different ways."""
    tags = [
        tag(327, "FB - Pageview", "html",
            {"html": "fbq('init','1560938438095658');"}, ("10",)),
        tag(400, "Meta - Base", META_TYPE,
            {"pixelId": "1560938438095658", "standardEventName": "PageView"}, ("20",)),
    ]
    result = collect_findings(tags, with_roles(**{"400": "setup"}))
    assert result["group_count"] == 1
    group = result["groups"][0]
    assert group["kind"] == "base"
    assert group["severity"] == "critical"
    assert "more than one way" in group["why"]


def test_two_base_tags_on_one_trigger_are_critical():
    tags = [
        tag(1, "A", "html", {"html": "fbq('init','123456789012345');"}, ("50",)),
        tag(2, "B", "html", {"html": "fbq('init','123456789012345');"}, ("50",)),
    ]
    group = collect_findings(tags, CONTEXT)["groups"][0]
    assert group["severity"] == "critical"
    assert "same trigger" in group["why"]


def test_two_base_tags_on_different_triggers_are_high():
    """Possible with mutually exclusive triggers, but rare enough to report."""
    tags = [
        tag(1, "A", "html", {"html": "fbq('init','123456789012345');"}, ("50",)),
        tag(2, "B", "html", {"html": "fbq('init','123456789012345');"}, ("60",)),
    ]
    group = collect_findings(tags, CONTEXT)["groups"][0]
    assert group["severity"] == "high"
    assert "mutually exclusive" in group["why"]


def test_different_accounts_of_one_vendor_are_not_duplicates():
    tags = [
        tag(1, "Pixel A", "html", {"html": "fbq('init','111111111111111');"}),
        tag(2, "Pixel B", "html", {"html": "fbq('init','222222222222222');"}),
    ]
    assert collect_findings(tags, CONTEXT)["clean"]


def test_paused_base_tags_do_not_create_a_finding():
    tags = [
        tag(1, "Live", "html", {"html": "fbq('init','123456789012345');"}),
        tag(2, "Paused", "html", {"html": "fbq('init','123456789012345');"}, paused=True),
    ]
    assert collect_findings(tags, CONTEXT)["clean"]


# ---------------------------------------------------------------------------
# Conversion tags do carry their own configuration
# ---------------------------------------------------------------------------


def test_identical_conversions_on_different_triggers_are_medium():
    """Reported so the user knows, not corrected: this is often deliberate."""
    tags = [
        tag(356, "Conv ES", "awct",
            {"conversionId": "16474873505", "conversionLabel": "5jhE"}, ("318",)),
        tag(532, "Conv pageview", "awct",
            {"conversionId": "16474873505", "conversionLabel": "5jhE"}, ("521",)),
    ]
    group = collect_findings(tags, CONTEXT)["groups"][0]
    assert group["kind"] == "conversion"
    assert group["severity"] == "medium"
    assert "Legitimate" in group["why"]


def test_identical_conversions_on_one_trigger_are_critical():
    tags = [
        tag(1, "A", "awct", {"conversionId": "1", "conversionLabel": "x"}, ("50",)),
        tag(2, "B", "awct", {"conversionId": "1", "conversionLabel": "x"}, ("50",)),
    ]
    assert collect_findings(tags, CONTEXT)["groups"][0]["severity"] == "critical"


def test_conversions_differing_in_label_are_not_duplicates():
    tags = [
        tag(1, "A", "awct", {"conversionId": "1", "conversionLabel": "x"}),
        tag(2, "B", "awct", {"conversionId": "1", "conversionLabel": "y"}),
    ]
    assert collect_findings(tags, CONTEXT)["clean"]


def test_ga4_events_are_deliberately_not_conversion_configs():
    assert conversion_config_of(tag(1, "x", "gaawe", {"eventName": "click"})) is None
    assert conversion_config_of(
        tag(2, "y", "awct", {"conversionId": "1", "conversionLabel": "z"})
    ) == ("google_ads_conversion", ("1", "z"))


# ---------------------------------------------------------------------------
# Coverage beyond the registry
# ---------------------------------------------------------------------------


VENDOR_INITS = {
    "meta": ("fbq('init', '1560938438095658');", "1560938438095658"),
    "tiktok": ('ttq.load("CQ1FCFBC77UEB9QOK980");', "CQ1FCFBC77UEB9QOK980"),
    "pinterest": ("pintrk('load', '2613821312747');", "2613821312747"),
    "linkedin": ('_linkedin_partner_id = "5919468";', "5919468"),
    "snapchat": ("snaptr('init','abc-def-123456');", "abc-def-123456"),
    "microsoft_ads": ('o={ti:"97012345", enableAutoSpaTracking:true};', "97012345"),
    "x_twitter": ("twq('config','o1a2b');", "o1a2b"),
    "reddit": ("rdt('init','t2_abc123');", "t2_abc123"),
    "criteo": ('{ event: "setAccount", account: 12345 }', "12345"),
    "taboola": ("_tfa.push({notify:'event', name:'page_view', id:1234567});", "1234567"),
    "outbrain": ("obApi('init', 'ABC123DEF');", "ABC123DEF"),
    "adroll": ('adroll_adv_id = "ABCDEF123";', "ABCDEF123"),
    "quora": ("qp('init','abcdef0123456789');", "abcdef0123456789"),
    "yandex_metrica": ('ym(12345678, "init", {clickmap:true});', "12345678"),
    "hotjar": ("h._hjSettings={hjid:1234567,hjsv:6};", "1234567"),
    "clarity": ('t.src="https://www.clarity.ms/tag/"+i;', None),
    "hubspot": ('src="//js.hs-scripts.com/1234567.js"', "1234567"),
    "klaviyo": (
        'src="https://static.klaviyo.com/onsite/js/klaviyo.js?company_id=AbC123"',
        "AbC123",
    ),
    "segment": ('analytics.load("abcdefghij0123456789");', "abcdefghij0123456789"),
    "mixpanel": ("mixpanel.init('0123456789abcdef0123456789abcdef');",
                 "0123456789abcdef0123456789abcdef"),
    "awin": ('src="https://www.dwin1.com/12345.js"', "12345"),
    "rakuten": ('src="//tag.rmp.rakuten.com/123456.ct.js"', "123456"),
    "line": ("_lt('init', {customerType: 'lap', tagId: 'abc-123'});", "abc-123"),
    "adform": ("pm('setup', '1234567');", "1234567"),
}


def test_the_registry_covers_far_more_than_the_advertising_majors():
    """Other users' containers carry vendors this one has never seen."""
    assert len(MEDIA_PLATFORMS) >= 30, "the registry should be broad, not just the majors"


def test_each_registered_vendor_is_recognised_from_its_init_call():
    for platform, (snippet, expected) in VENDOR_INITS.items():
        if expected is None:
            continue  # clarity's id comes from a concatenated URL, covered below
        found = dict(find_initialisations(snippet))
        assert found.get(platform) == expected, (
            f"{platform}: expected {expected}, got {found}"
        )


def test_image_pixel_urls_are_recognised():
    """A noscript fallback is a plain URL in a Custom Image tag's `url`."""
    for url, expected in {
        "https://www.facebook.com/tr?id=123456789012345&ev=PageView": ("meta", "123456789012345"),
        "https://ct.pinterest.com/v3/?tid=2612427802921&event=checkout": ("pinterest", "2612427802921"),
        "https://px.ads.linkedin.com/collect/?pid=5919468&fmt=gif": ("linkedin", "5919468"),
        "https://bat.bing.com/action/0?ti=97012345&Ver=2": ("microsoft_ads", "97012345"),
        "https://www.clarity.ms/tag/azkgi4pvk3": ("clarity", "azkgi4pvk3"),
    }.items():
        assert dict(find_initialisations(url)).get(expected[0]) == expected[1], url


def test_double_quoted_snippets_match():
    """Patterns were once matched against a JSON dump, which escapes quotes.

    `json.dumps` turns `"5919468"` into `\\"5919468\\"`, so every double-quoted
    snippet stopped matching. Meta kept working only because its snippet uses
    single quotes, which hid the fault -- LinkedIn, Microsoft and Criteo were
    all silently invisible.
    """
    for platform, (snippet, expected) in VENDOR_INITS.items():
        if expected is None or '"' not in snippet:
            continue
        found = initialisations_of(tag(1, "V", "html", {"html": snippet}), **CONTEXT)
        assert any(i.account == expected for i in found), platform


def test_an_unknown_vendor_is_caught_by_script_similarity():
    """The platform nobody anticipated still cannot be installed twice."""
    snippet = (
        "<script>(function(w,d){var s=d.createElement('script');"
        "s.src='https://cdn.brandnewvendor.io/pixel.js?site=98765';"
        "s.async=true;d.head.appendChild(s);w.bnvq=w.bnvq||[];"
        "w.bnvq.push(['page_view']);})(window,document);</script>"
    )
    reformatted = snippet.replace(";", ";\n  ").replace("<script>", "<script>\n  ")

    assert script_fingerprint(snippet) == script_fingerprint(reformatted)

    tags = [
        tag(1, "Vendor A", "html", {"html": snippet}, ("10",)),
        tag(2, "Vendor A copy", "html", {"html": reformatted}, ("20",)),
    ]
    group = collect_findings(tags, CONTEXT)["groups"][0]
    assert group["kind"] == "script"
    assert group["severity"] == "high"


def test_variable_references_do_not_break_script_matching():
    base = "<script>window.vq=window.vq||[];window.vq.push(['id','%s']);"
    base += "var s=document.createElement('script');s.src='//cdn.x.io/p.js';</script>"
    assert script_fingerprint(base % "{{Account}}") == script_fingerprint(base % "{{Other}}")


def test_a_short_script_is_not_fingerprinted():
    """Two one-liners are not evidence of a duplicated vendor."""
    assert script_fingerprint("<script>x()</script>") is None
    assert html_fingerprint(tag(1, "T", "html", {"html": "<script>x()</script>"})) is None


def test_constants_are_resolved_so_a_variable_matches_a_literal():
    tags = [
        tag(1, "By variable", META_TYPE, {"pixelId": "{{CONST - Meta Pixel}}"}, ("10",)),
        tag(2, "By literal", "html", {"html": "fbq('init','1560938438095658');"}, ("20",)),
    ]
    result = collect_findings(tags, with_roles(**{"1": "setup"}))
    assert result["group_count"] == 1
    assert result["groups"][0]["severity"] == "critical"


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
