"""Third-party media platforms that require a setup (base) tag.

Meta, TikTok, Pinterest, LinkedIn and the rest all follow the same shape as
Google: a base tag loads the pixel library and registers the account id, and
every event tag afterwards assumes that library is already on the page. Firing
`Purchase` for TikTok with no `ttq.load()` before it produces exactly the
Google failure mode -- a tag that exists, looks right, and sends nothing.

Detection is harder here than for Google tags. These pixels arrive as community
templates whose API type is `cvt_<galleryTemplateId>` -- which says nothing
about the vendor unless you look the template up -- or as Custom HTML. So
signals are weighed by strength:

STRONG (one is enough)
  1. the tag's type maps to an installed gallery template whose owner or
     repository names the platform, from `templates().list()`
  2. the vendor's own snippet inside Custom HTML (`ttq.load(`, `fbq('init'`)

WEAK (two are needed)
  3. a parameter name claimed by exactly one platform and by no native Google
     tag (`pixel_code`, `partnerId`)
  4. the tag name

Names shared between platforms -- `tagId`, `pixelId`, `advertiserId` -- prove
nothing on their own. `tagId` alone belongs to Pinterest, to Microsoft UET and
to Google's `googtag`, and once counted as evidence it made a container with
one Google Tag report duplicate base pixels for two absent platforms. See
`ambiguous_id_parameters`.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class MediaPlatform:
    """How to recognise one advertising platform inside a container."""

    key: str
    label: str
    #: Gallery template owner/repository fragments, lowercased.
    gallery_markers: tuple[str, ...]
    #: Parameter keys that identify the platform's account id.
    id_parameters: tuple[str, ...]
    #: Substrings found in the Custom HTML implementation of the base pixel.
    html_base_markers: tuple[str, ...]
    #: Substrings that indicate an EVENT call rather than initialization.
    html_event_markers: tuple[str, ...] = ()
    #: Words in a tag name that suggest this platform.
    name_keywords: tuple[str, ...] = ()
    #: Words in a tag name that suggest it is the base/setup tag.
    base_keywords: tuple[str, ...] = field(
        default_factory=lambda: ("base", "setup", "init", "config", "pageview", "page view")
    )
    #: Template parameters that carry the event name. A tag that sets one of
    #: these to something other than a page view is an EVENT tag, not a setup
    #: tag -- without this, every Pinterest purchase tag reads as a duplicate
    #: base pixel.
    event_parameters: tuple[str, ...] = ()
    #: Values of those parameters that still mean "this is the base tag".
    base_event_values: tuple[str, ...] = ("pageview", "page_view", "pagevisit", "page_visit", "")
    id_format: str = ""
    setup_guidance: str = ""


MEDIA_PLATFORMS: dict[str, MediaPlatform] = {
    "meta": MediaPlatform(
        key="meta",
        event_parameters=("eventName", "standardEventName", "eecEventName"),
        label="Meta (Facebook) Pixel",
        # Confirmed live: gallery owner "facebook", repo
        # "GoogleTagManager-WebTemplate-For-FacebookPixel".
        gallery_markers=(
            "facebook",
            "facebookincubator",
            "meta-pixel",
            "meta pixel",
        ),
        # Confirmed live: the official template's required params are
        # `pixelId` and `advancedMatchingList`.
        id_parameters=("pixelId", "pixelID", "metaPixelId", "facebookPixelId"),
        html_base_markers=("fbq('init'", 'fbq("init"', "connect.facebook.net/en_US/fbevents.js", "fbq('set'"),
        html_event_markers=("fbq('track'", 'fbq("track"', "fbq('trackCustom'"),
        name_keywords=("meta", "facebook", "fb "),
        id_format="15-16 digit numeric pixel id",
        setup_guidance=(
            "Install the Meta Pixel template from the Community Template "
            "Gallery, or create a Custom HTML base tag containing "
            "fbq('init', '<PIXEL_ID>') on Initialization - All Pages. Event "
            "tags then call fbq('track', 'Purchase', {...})."
        ),
    ),
    "tiktok": MediaPlatform(
        key="tiktok",
        event_parameters=("event",),
        label="TikTok Pixel",
        # Confirmed live: gallery owner "tiktok", repo "gtm-template-pixel".
        gallery_markers=("tiktok", "bytedance"),
        # Confirmed live: the official template uses snake_case `pixel_code`,
        # NOT `pixelCode`. It marks nothing required, so a tag with no pixel
        # code is accepted and silently sends nothing.
        id_parameters=("pixel_code", "pixelCode", "tiktokPixelCode"),
        html_base_markers=("ttq.load(", "analytics.tiktok.com/i18n/pixel", "ttq.page("),
        html_event_markers=("ttq.track(", "ttq.instance("),
        name_keywords=("tiktok", "tt "),
        id_format="20-character alphanumeric pixel code (e.g. C4A1B2C3D4E5F6G7H8I9)",
        setup_guidance=(
            "Install the official TikTok Pixel template from the Community "
            "Template Gallery and configure it with the Pixel Code on "
            "Initialization - All Pages, or create a Custom HTML base tag "
            "containing ttq.load('<PIXEL_CODE>'); ttq.page();. Event tags then "
            "call ttq.track('CompletePayment', {...})."
        ),
    ),
    "pinterest": MediaPlatform(
        key="pinterest",
        event_parameters=("eventName", "adeEventName"),
        label="Pinterest Tag",
        # Confirmed live: gallery owner "pinterest", repo "ws-gtm-template".
        gallery_markers=("pinterest",),
        # Confirmed live: required params are `tagId` and `adeEventName`.
        # NOTE `tagId` collides with googtag and Microsoft UET, so this signal
        # is only meaningful alongside the gallery owner or a name match.
        id_parameters=("tagId", "pinterestTagId", "tid"),
        html_base_markers=("pintrk('load'", 'pintrk("load"', "s.pinimg.com/ct/core.js", "pintrk('page'"),
        html_event_markers=("pintrk('track'", 'pintrk("track"'),
        name_keywords=("pinterest", "pintrk"),
        id_format="13-digit numeric tag id",
        setup_guidance=(
            "Install the Pinterest Tag template from the gallery, or create a "
            "Custom HTML base tag with pintrk('load', '<TAG_ID>'); "
            "pintrk('page'); on Initialization - All Pages."
        ),
    ),
    "linkedin": MediaPlatform(
        key="linkedin",
        event_parameters=("conversionId",),
        label="LinkedIn Insight Tag",
        gallery_markers=("linkedin",),
        id_parameters=("partnerId", "linkedInPartnerId", "partner_id"),
        html_base_markers=("_linkedin_partner_id", "snap.licdn.com/li.lms-analytics/insight.min.js"),
        html_event_markers=("lintrk('track'", 'lintrk("track"'),
        name_keywords=("linkedin", "insight tag"),
        id_format="6-8 digit numeric partner id",
        setup_guidance=(
            "Install the LinkedIn Insight Tag template from the gallery, or "
            "create a Custom HTML base tag setting _linkedin_partner_id on "
            "Initialization - All Pages. Conversions then use "
            "lintrk('track', {conversion_id: N})."
        ),
    ),
    "snapchat": MediaPlatform(
        key="snapchat",
        # Confirmed live: the gallery template uses `accountId` and
        # `eventName` -- not the `pixelId`/`eventType` a vendor-agnostic
        # guess would suggest. Template-derived hints override this.
        event_parameters=("eventName", "eventType"),
        label="Snap Pixel",
        gallery_markers=("snapchat", "snap-"),
        id_parameters=("accountId", "pixelId", "snapPixelId"),
        html_base_markers=("snaptr('init'", 'snaptr("init"', "sc-static.net/scevent.min.js"),
        html_event_markers=("snaptr('track'", 'snaptr("track"'),
        name_keywords=("snapchat", "snap pixel"),
        id_format="UUID-style pixel id",
        setup_guidance=(
            "Install the Snap Pixel template from the gallery, or create a "
            "Custom HTML base tag with snaptr('init', '<PIXEL_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    "microsoft_ads": MediaPlatform(
        key="microsoft_ads",
        event_parameters=("eventAction", "eventCategory", "eventLabel"),
        label="Microsoft Advertising UET",
        gallery_markers=("microsoft", "bing"),
        id_parameters=("tagId", "uetTagId", "ti"),
        html_base_markers=("uetq", "bat.bing.com/bat.js", "UET("),
        html_event_markers=("uetq.push('event'", 'uetq.push("event"'),
        name_keywords=("microsoft", "bing", "uet"),
        id_format="8-9 digit numeric UET tag id",
        setup_guidance=(
            "Install the Microsoft Advertising UET template from the gallery, "
            "or create a Custom HTML base tag with the UET snippet on "
            "Initialization - All Pages."
        ),
    ),
    "x_twitter": MediaPlatform(
        key="x_twitter",
        event_parameters=("eventId",),
        label="X (Twitter) Pixel",
        gallery_markers=("twitter", "x-corp"),
        id_parameters=("pixelId", "twitterPixelId"),
        html_base_markers=("twq('config'", 'twq("config"', "static.ads-twitter.com/uwt.js", "twq('init'"),
        html_event_markers=("twq('event'", 'twq("event"'),
        name_keywords=("twitter", "x pixel", "x ads"),
        id_format="alphanumeric pixel id (e.g. o1a2b)",
        setup_guidance=(
            "Install the X Pixel template from the gallery, or create a Custom "
            "HTML base tag with twq('config', '<PIXEL_ID>') on Initialization "
            "- All Pages."
        ),
    ),
    "reddit": MediaPlatform(
        key="reddit",
        # Confirmed live: required param is `id`, event is `eventType`.
        event_parameters=("eventType", "customEventName"),
        label="Reddit Pixel",
        gallery_markers=("reddit",),
        id_parameters=("id", "advertiserId", "redditPixelId"),
        html_base_markers=("rdt('init'", 'rdt("init"', "www.redditstatic.com/ads/pixel.js"),
        html_event_markers=("rdt('track'", 'rdt("track"'),
        name_keywords=("reddit", "rdt"),
        id_format="advertiser id starting with t2_",
        setup_guidance=(
            "Install the Reddit Pixel template from the gallery, or create a "
            "Custom HTML base tag with rdt('init', '<ADVERTISER_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    "criteo": MediaPlatform(
        key="criteo",
        event_parameters=("eventType",),
        label="Criteo OneTag",
        gallery_markers=("criteo",),
        # Confirmed live: the Criteo Loader template uses `partnerId` and
        # declares no event parameter at all, which is what marks it a loader.
        id_parameters=("partnerId", "accountId", "caccount", "criteoAccountId"),
        html_base_markers=("static.criteo.net/js/ld/ld.js", "criteo_q"),
        html_event_markers=("{ event: \"viewItem\"", "{ event: \"trackTransaction\""),
        name_keywords=("criteo",),
        id_format="5-6 digit numeric account id",
        setup_guidance=(
            "Install the Criteo OneTag template from the gallery, or create a "
            "Custom HTML base tag loading ld.js with the account id."
        ),
    ),
}


def platform_keys() -> list[str]:
    return list(MEDIA_PLATFORMS)


def ambiguous_id_parameters() -> set[str]:
    """Parameter names too generic to identify a platform on their own.

    `tagId` belongs to Pinterest, to Microsoft UET *and* to Google's own
    `googtag`. Treating it as evidence made a container with one Google Tag and
    one Pinterest tag report duplicate base pixels for two platforms that were
    not there. A name is ambiguous when more than one platform claims it, or
    when a native Google tag type already uses it.

    Computed rather than hardcoded so that adding a platform cannot silently
    reintroduce the collision.
    """
    from collections import Counter

    from .tag_specs import TAG_SPECS

    counts = Counter(
        name for platform in MEDIA_PLATFORMS.values() for name in platform.id_parameters
    )
    shared = {name for name, total in counts.items() if total > 1}
    native = {key for spec in TAG_SPECS.values() for key in spec.known}
    return shared | (native & set(counts))


def match_platform_in_text(text: str) -> list[tuple[str, str]]:
    """Return (platform_key, signal) pairs found in a blob of tag text."""
    lowered = text.lower()
    hits: list[tuple[str, str]] = []
    for key, platform in MEDIA_PLATFORMS.items():
        for marker in platform.html_base_markers:
            if marker.lower() in lowered:
                hits.append((key, f"base snippet marker '{marker}'"))
                break
        for marker in platform.html_event_markers:
            if marker.lower() in lowered:
                hits.append((key, f"event call marker '{marker}'"))
                break
    return hits
