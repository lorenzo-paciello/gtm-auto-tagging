"""Every registered platform, against a snippet resembling the real thing.

Three things are checked for each vendor, because each has broken in practice:

1. **The base snippet is recognised and the account id is captured.** A pattern
   that matches nothing is worse than no pattern -- it looks like coverage.
2. **No other platform matches it.** Regexes for 35 vendors share a namespace;
   a loose one (`app_id`, `ti:`, `id:`) quietly attributes half the container
   to the wrong tool.
3. **The event snippet is NOT read as an initialisation.** This is the whole
   point of the redesign: an event tag carries no account, so treating one as a
   base tag reports every purchase tag in the container as a duplicate pixel.

Point 3 has a nasty corner. Several vendors put an event-shaped call inside
their own base snippet -- Taboola pushes `name: 'page_view'`, AdRoll's loader
calls `__adroll.record_user`, VK's base ends with `VK.Retargeting.Hit()`,
Criteo's homepage tag pushes `viewHome` next to `setAccount`. Each of those,
with a naive event pattern, made the base tag invisible. The base-snippet
assertions below are what catch that.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gtm_agent.tools.media_platforms import MEDIA_PLATFORMS  # noqa: E402
from gtm_agent.tools.media_platforms import ambiguous_id_parameters  # noqa: E402
from gtm_agent.tools.vendor_snippets import event_signal  # noqa: E402
from gtm_agent.tools.vendor_snippets import find_event_only_platforms  # noqa: E402
from gtm_agent.tools.vendor_snippets import find_initialisations  # noqa: E402
from gtm_agent.tools.vendor_snippets import init_signal  # noqa: E402
from gtm_agent.tools.vendor_snippets import platform_label  # noqa: E402

#: platform -> (base snippet, expected account id, event snippet or None)
#: Snippets are trimmed versions of each vendor's published install code.
SNIPPETS: dict[str, tuple[str, str, str | None]] = {
    "meta": (
        """!function(f,b,e,v,n,t,s){...}(window,document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        fbq('init', '156914648903155'); fbq('track', 'PageView');""",
        "156914648903155",
        "fbq('track', 'Purchase', {value: 10.00, currency: 'BRL'});",
    ),
    "tiktok": (
        """!function(w,d,t){w.TiktokAnalyticsObject=t;...}(window,document,'ttq');
        ttq.load('C4A1B2C3D4E5F6G7H8I9'); ttq.page();""",
        "C4A1B2C3D4E5F6G7H8I9",
        "ttq.track('CompletePayment', {value: 10, currency: 'BRL'});",
    ),
    "pinterest": (
        """!function(e){if(!window.pintrk){...}}();
        pintrk('load', '2613960819420'); pintrk('page');""",
        "2613960819420",
        "pintrk('track', 'checkout', {value: 10, order_quantity: 1});",
    ),
    "linkedin": (
        """_linkedin_partner_id = "1234567";
        window._linkedin_data_partner_ids.push(_linkedin_partner_id);
        b.src = "https://snap.licdn.com/li.lms-analytics/insight.min.js";""",
        "1234567",
        "window.lintrk('track', { conversion_id: 987654 });",
    ),
    "snapchat": (
        """(function(e,t,n){...})(window,document,'https://sc-static.net/scevent.min.js');
        snaptr('init', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890');
        snaptr('track', 'PAGE_VIEW');""",
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "snaptr('track', 'PURCHASE', {price: 10, currency: 'BRL'});",
    ),
    "microsoft_ads": (
        """(function(w,d,t,r,u){...})(window,document,"script",
        "//bat.bing.com/bat.js","uetq");
        var o={ti:"187012345", enableAutoSpaTracking: true};""",
        "187012345",
        "window.uetq.push('event', 'purchase', {revenue_value: 10});",
    ),
    "x_twitter": (
        """!function(e,t,n,s,u,a){...}(window,document,'script');
        twq('config','o1a2b');""",
        "o1a2b",
        "twq('event', 'tw-o1a2b-o9x8y', {value: 10});",
    ),
    "reddit": (
        """!function(w,d){...}(window,document);
        rdt('init','t2_abc123def'); rdt('track', 'PageVisit');""",
        "t2_abc123def",
        "rdt('track', 'Purchase', {value: 10, currency: 'BRL'});",
    ),
    "criteo": (
        """window.criteo_q = window.criteo_q || [];
        window.criteo_q.push(
          { event: "setAccount", account: 12345 },
          { event: "setSiteType", type: "d" },
          { event: "viewHome" });""",
        "12345",
        """window.criteo_q.push(
          { event: "setAccount", account: 12345 },
          { event: "viewItem", item: "SKU-1" });""",
    ),
    "taboola": (
        """window._tfa = window._tfa || [];
        window._tfa.push({notify: 'event', name: 'page_view', id: 1234567});
        !function(t,f,a,x){...}(document.createElement('script'),
        '//cdn.taboola.com/libtrc/unip/1234567/tfa.js');""",
        "1234567",
        "_tfa.push({notify: 'event', name: 'make_purchase', id: 1234567});",
    ),
    "outbrain": (
        """/** DO NOT MODIFY */ !function(_window, _document){...}(window, document);
        obApi('init', '00a1b2c3d4e5');""",
        "00a1b2c3d4e5",
        "obApi('track', 'Purchase');",
    ),
    "adroll": (
        """adroll_adv_id = "ABCDEFGHIJKLMNOPQRSTUV";
        adroll_pix_id = "VUTSRQPONMLKJIHGFEDCBA";
        (function () { ... __adroll.record_user({"adroll_segments": ""}); })();""",
        "ABCDEFGHIJKLMNOPQRSTUV",
        """adroll_adv_id = "ABCDEFGHIJKLMNOPQRSTUV";
        adroll_segments = "purchase_segment";""",
    ),
    "quora": (
        """!function(q,e,v,n,t,s){...}(window, document);
        qp('init', 'a1b2c3d4e5f60718293a4b5c6d7e8f90'); qp('track', 'ViewContent');""",
        "a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "qp('track', 'Purchase', {value: 10});",
    ),
    "amazon_ads": (
        """!function(a,b,c){...}(window,document,"script");
        amzn("setRegion","NA"); amzn("addTag","a1b2c3d4-5678-90ab-cdef-1234567890ab");""",
        "a1b2c3d4-5678-90ab-cdef-1234567890ab",
        "amzn('trackEvent', 'purchase', {value: 10});",
    ),
    "adform": (
        """window._adftrack = { pm: 1234567, divider: encodeURIComponent('|'),
        pagename: encodeURIComponent('home') };
        (function(){var s=document.createElement('script'); ...})();""",
        "1234567",
        None,
    ),
    "rtb_house": (
        """(function(w,d,dn,t){...})(window, document, 'script',
        'https://tags.creativecdn.com/aBcDeF12345.js');""",
        "aBcDeF12345",
        None,
    ),
    "teads": (
        """window.teads_analytics = window.teads_analytics || {};
        teads_analytics.analytics_tag_id = "PIXEL";
        window.teads_analytics.analytics_tag_id = '12345';""",
        "12345",
        None,
    ),
    "awin": (
        """<script defer src="https://www.dwin1.com/12345.js" type="text/javascript"></script>""",
        "12345",
        None,
    ),
    "rakuten": (
        """<script src="https://tag.rmp.rakuten.com/123456.ct.js"></script>""",
        "123456",
        None,
    ),
    "impact": (
        """<script src="https://utt.impactcdn.com/A1234567-89ab-cdef-0123-456789abcdef1.js"></script>""",
        "A1234567-89ab-cdef-0123-456789abcdef1",
        None,
    ),
    "yandex_metrica": (
        """(function(m,e,t,r,i,k,a){...})(window,document,'script',
        'https://mc.yandex.ru/metrika/tag.js', 'ym');
        ym(87654321, 'init', {clickmap:true, trackLinks:true});""",
        "87654321",
        "ym(87654321, 'reachGoal', 'purchase');",
    ),
    "line": (
        """(function(g,d,o){...})(window, document);
        _lt('init', {customerType: 'account', tagId: 'abcd1234-ef56'});
        _lt('send', 'pv', ['abcd1234-ef56']);""",
        "abcd1234-ef56",
        "_lt('send', 'cv', {type: 'Conversion'}, ['abcd1234-ef56']);",
    ),
    "kakao": (
        """<script src="//t1.daumcdn.net/kas/static/kp.js"></script>
        <script>kakaoPixel('1234567890123').pageView();</script>""",
        "1234567890123",
        "kakaoPixel('1234567890123').purchase({total_quantity: '1'});",
    ),
    "naver": (
        """if (!wcs_add) var wcs_add = {};
        wcs_add["wa"] = "s_1a2b3c4d5e6f";
        if (!_nasa) var _nasa = {};
        wcs.inflow(); wcs_do(_nasa);""",
        "s_1a2b3c4d5e6f",
        """wcs_add["wa"] = "s_1a2b3c4d5e6f";
        var _conv = {}; _conv["cnv"] = wcs.cnv("1","10000"); wcs.trans(_conv);""",
    ),
    "vk": (
        """!function(){var t=document.createElement("script");...}();
        VK.Retargeting.Init("VK-RTRG-123456-abcDE"); VK.Retargeting.Hit();""",
        "VK-RTRG-123456-abcDE",
        """VK.Retargeting.Init("VK-RTRG-123456-abcDE");
        VK.Goal("purchase", {value: 10});""",
    ),
    "hubspot": (
        """<script type="text/javascript" id="hs-script-loader" async defer
        src="//js.hs-scripts.com/1234567.js"></script>""",
        "1234567",
        "var _hsq = window._hsq = window._hsq || []; _hsq.push(['trackEvent', {id: 'x'}]);",
    ),
    "klaviyo": (
        """<script async type="text/javascript"
        src="https://static.klaviyo.com/onsite/js/klaviyo.js?company_id=AbC123"></script>""",
        "AbC123",
        "_learnq.push(['track', 'Placed Order', {$value: 10}]);",
    ),
    "segment": (
        """!function(){var analytics=window.analytics=window.analytics||[];...
        analytics.load("aBcDeF1234567890GhIjKl"); analytics.page();}();""",
        "aBcDeF1234567890GhIjKl",
        "analytics.track('Order Completed', {revenue: 10});",
    ),
    "mixpanel": (
        """(function(f,b){...})(document,window.mixpanel||[]);
        mixpanel.init("0123456789abcdef0123456789abcdef", {debug: false});""",
        "0123456789abcdef0123456789abcdef",
        "mixpanel.track('Purchase', {value: 10});",
    ),
    "amplitude": (
        """(function(e,t){...})(window,document);
        amplitude.getInstance().init("fedcba9876543210fedcba9876543210");""",
        "fedcba9876543210fedcba9876543210",
        "amplitude.getInstance().logEvent('Purchase', {value: 10});",
    ),
    "hotjar": (
        """(function(h,o,t,j,a,r){h.hj=h.hj||function(){...};
        h._hjSettings={hjid:1234567,hjsv:6};
        a.src=t+h._hjSettings.hjid+j;})(window,document,
        'https://static.hotjar.com/c/hotjar-','.js?sv=');""",
        "1234567",
        None,
    ),
    "clarity": (
        """(function(c,l,a,r,i,t,y){...})(window, document, "clarity", "script",
        "a1b2c3d4e5");
        t.src="https://www.clarity.ms/tag/a1b2c3d4e5";""",
        "a1b2c3d4e5",
        None,
    ),
    "crazy_egg": (
        """<script type="text/javascript"
        src="//script.crazyegg.com/pages/scripts/0012/3456.js" async="async"></script>""",
        "0012/3456",
        None,
    ),
    "lucky_orange": (
        """<script async defer
        src="https://tools.luckyorange.com/core/lo.js?site-id=a1b2c3d4"></script>""",
        "a1b2c3d4",
        None,
    ),
    "intercom": (
        """window.intercomSettings = { app_id: "abc12345" };
        (function(){var w=window;var ic=w.Intercom; ...})();""",
        "abc12345",
        None,
    ),
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


# ---------------------------------------------------------------------------
# 1. Every platform in the registry has a snippet here.
# ---------------------------------------------------------------------------
missing = set(MEDIA_PLATFORMS) - set(SNIPPETS)
check(not missing, f"platforms with no snippet under test: {sorted(missing)}")
unknown = set(SNIPPETS) - set(MEDIA_PLATFORMS)
check(not unknown, f"snippets for unregistered platforms: {sorted(unknown)}")


# ---------------------------------------------------------------------------
# 2. The base snippet is recognised, with the right account id, and by nobody
#    else.
# ---------------------------------------------------------------------------
for key, (base, expected_id, event) in SNIPPETS.items():
    if key not in MEDIA_PLATFORMS:
        continue
    found = dict(find_initialisations(base))

    check(key in found, f"{key}: base snippet not recognised as an initialisation")
    if key in found:
        check(
            found[key] == expected_id,
            f"{key}: captured account id {found[key]!r}, expected {expected_id!r}",
        )

    others = sorted(set(found) - {key})
    check(
        not others,
        f"{key}: base snippet also matched {others} -- a pattern is too loose",
    )

    check(
        init_signal(key, base) is not None,
        f"{key}: init_signal found nothing in the base snippet",
    )


# ---------------------------------------------------------------------------
# 3. An event snippet initialises nothing, and is attributed to its vendor.
# ---------------------------------------------------------------------------
for key, (_base, _expected, event) in SNIPPETS.items():
    if key not in MEDIA_PLATFORMS or event is None:
        continue

    initialised = dict(find_initialisations(event))
    check(
        key not in initialised,
        f"{key}: event snippet read as an initialisation (account "
        f"{initialised.get(key)!r}) -- every event tag would report as a "
        "duplicate base pixel",
    )
    check(
        not initialised,
        f"{key}: event snippet initialised {sorted(initialised)}",
    )

    check(
        key in find_event_only_platforms(event),
        f"{key}: event snippet not attributed to the platform, so a tag "
        "depending on a missing base tag would go unreported",
    )
    check(
        event_signal(key, event) is not None,
        f"{key}: event_signal found nothing in the event snippet",
    )


# ---------------------------------------------------------------------------
# 4. Registry invariants.
# ---------------------------------------------------------------------------
for key, platform in MEDIA_PLATFORMS.items():
    check(platform.key == key, f"{key}: key field disagrees with its dict key")
    check(
        platform.event_model in ("library", "standalone", "single"),
        f"{key}: unknown event_model {platform.event_model!r}",
    )
    check(bool(platform.label), f"{key}: no label")
    check(
        bool(platform.gallery_markers or platform.init),
        f"{key}: neither a gallery marker nor an init pattern -- undetectable",
    )
    check(
        bool(platform.setup_guidance),
        f"{key}: no setup_guidance, so a missing base tag has no remedy",
    )
    if platform.events_repeat_the_id:
        check(
            bool(platform.events),
            f"{key}: events_repeat_the_id with no event pattern vetoes nothing",
        )

# "line" is a substring of "linkedin"; a marker that short would attribute
# every LinkedIn template to LINE.
for key, platform in MEDIA_PLATFORMS.items():
    for marker in platform.gallery_markers + platform.name_keywords:
        for other_key, other in MEDIA_PLATFORMS.items():
            if other_key == key:
                continue
            check(
                marker not in other.label.lower(),
                f"{key}: marker {marker!r} also appears in {other_key}'s label "
                f"{other.label!r}",
            )

check(
    len(MEDIA_PLATFORMS) >= 30,
    "the registry should be broad, not just the advertising majors",
)
check(
    len([p for p in MEDIA_PLATFORMS.values() if p.event_model == "library"]) >= 25,
    "most platforms load a library their event tags depend on",
)
check(
    platform_label("meta") == "Meta (Facebook) Pixel",
    "platform_label should resolve a registered key",
)
check(
    platform_label("not_a_platform") == "not_a_platform",
    "platform_label should fall back to the key it was given",
)

# With 35 platforms these names are claimed by several vendors and prove
# nothing on their own. `tagId` is the one that once made a lone Google Tag
# report as a duplicate Pinterest AND Microsoft base pixel.
ambiguous = ambiguous_id_parameters()
for name in ("tagId", "pixelId", "accountId", "advertiserId", "id"):
    check(name in ambiguous, f"{name!r} should be treated as ambiguous")


# ---------------------------------------------------------------------------
# 5. A vendor in no registry still fingerprints.
# ---------------------------------------------------------------------------
from gtm_agent.tools.vendor_snippets import script_fingerprint  # noqa: E402

unregistered = """
<script>
  (function(w,d){var s=d.createElement('script');
   s.src='https://cdn.obscure-vendor.example/pixel.js?acct=99887766';
   s.async=true;d.head.appendChild(s);
   w.obscureQueue=w.obscureQueue||[];w.obscureQueue.push(['page']);})(window,document);
</script>
"""
check(
    script_fingerprint(unregistered) is not None,
    "an unregistered vendor's snippet should still fingerprint",
)
check(
    script_fingerprint(unregistered)
    == script_fingerprint(unregistered.replace("\n", " ").replace("  ", "")),
    "reformatting a snippet must not change its fingerprint",
)
check(
    not find_initialisations(unregistered),
    "an unregistered vendor must not be attributed to a registered one",
)


print(f"{len(failures)} failure(s)")
for failure in failures:
    print("  -", failure)
sys.exit(1 if failures else 0)
