"""The one registry of third-party media platforms.

Every part of the agent that has to answer "which vendor is this tag, and is it
the base tag?" reads this file: the prerequisite check before a tag is created,
the media detection in listings, the identity audit, and duplicate detection.
There used to be two registries -- a short one here for prerequisites and a
longer one for duplicates -- and they drifted: a container could be told its
Taboola pixel was installed twice while the creator agent had never heard of
Taboola and happily added a third.

## The shape every platform shares

A base tag loads the vendor's library and registers the account id; every event
tag afterwards assumes that library is already on the page:

    fbq('init', '123')            <- the account lives here
    fbq('track', 'AddToCart')     <- no account; uses the pixel above

That is why `event_model` matters. Firing `Purchase` for TikTok with no
`ttq.load()` before it produces a tag that exists, looks right and sends
nothing. But it is not universal: an Awin sale tag is self-contained, and
Hotjar has no event tags at all. Reporting "missing base tag" for those would
be a fault the agent invented.

## Recognising a platform

Community templates are opaque -- the API type is `cvt_<galleryTemplateId>`,
which names no vendor -- so signals are weighed by strength:

STRONG (one is enough)
  1. the tag's type maps to an installed gallery template whose owner or
     repository names the platform, from `templates().list()`
  2. the vendor's own initialisation or event call inside Custom HTML

WEAK (two are needed)
  3. a parameter name claimed by exactly one platform and by no native Google
     tag
  4. the tag name

Names shared between platforms -- `tagId`, `pixelId`, `accountId` -- prove
nothing on their own. `tagId` alone belongs to Pinterest, to Microsoft UET and
to Google's `googtag`, and once counted as evidence it made a container with
one Google Tag report duplicate base pixels for two absent platforms. See
`ambiguous_id_parameters`, which computes that set rather than hardcoding it,
so adding a platform cannot silently reintroduce the collision.

## Adding a platform

One entry. Fill in what is known and leave the rest empty -- a platform with
only `init` patterns still participates in duplicate detection, and one with
only `gallery_markers` still participates in prerequisite checks. The regexes
must capture the ACCOUNT ID as group 1, and must match an initialisation only:
matching `fbq('track', ...)` as if it configured an account would report every
event tag in the container as a base tag.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

#: How a platform's event tags relate to its base tag. This decides whether a
#: missing base tag is a fault at all.
#:
#: * ``library``    -- event tags call a library the base tag loaded. No base
#:                     tag means the event tags send nothing. The common case.
#: * ``standalone`` -- each tag is self-contained and carries its own account
#:                     id, as affiliate sale tags do. There is nothing to be
#:                     missing, so no prerequisite is reported.
#: * ``single``     -- one install tag and no event tags at all (session
#:                     recording, heatmaps). Worth checking it fires on every
#:                     page; nothing depends on it.
EVENT_MODELS = ("library", "standalone", "single")

_DEFAULT_BASE_KEYWORDS = (
    "base",
    "setup",
    "init",
    "config",
    "pageview",
    "page view",
    "all pages",
)


@dataclass(frozen=True)
class MediaPlatform:
    """How to recognise one media platform inside a container."""

    key: str
    label: str
    #: See EVENT_MODELS. Decides whether a missing base tag is reported.
    event_model: str = "library"
    #: Gallery template owner/repository/name fragments, lowercased. Keep these
    #: unambiguous: "line" is a substring of "linkedin", so LINE uses
    #: "line tag" and "linecorp" instead.
    gallery_markers: tuple[str, ...] = ()
    #: Parameter keys that may carry the platform's account id. Used to read a
    #: value once the tag is already attributed to the platform, and -- when
    #: the name is claimed by no one else -- as a weak identification signal.
    id_parameters: tuple[str, ...] = ()
    #: Regexes matching the INITIALISATION call, capturing the account id as
    #: group 1. Ordered most specific first; the first to match wins.
    init: tuple[str, ...] = ()
    #: Regexes matching a call that uses an already-loaded library. Present so
    #: an event-only tag is recognised as the vendor's without being mistaken
    #: for a base tag.
    events: tuple[str, ...] = ()
    #: True when the vendor repeats the account id in every call, so matching
    #: an init pattern is not proof of initialisation. Taboola's event push
    #: carries `id:`, Criteo's often repeats `setAccount`, and Naver's
    #: conversion tag re-declares `wcs_add['wa']`. Without this, every one of
    #: their event tags reads as a duplicate base pixel.
    events_repeat_the_id: bool = False
    #: Words in a tag name that suggest this platform.
    name_keywords: tuple[str, ...] = ()
    #: Words in a tag name that suggest it is the base/setup tag.
    base_keywords: tuple[str, ...] = field(
        default_factory=lambda: _DEFAULT_BASE_KEYWORDS
    )
    #: Template parameters that carry the event name. A tag that sets one of
    #: these to something other than a page view is an EVENT tag, not a setup
    #: tag -- without this, every Pinterest purchase tag reads as a duplicate
    #: base pixel. The template's own contract wins where one is installed;
    #: this is the fallback for Custom HTML.
    event_parameters: tuple[str, ...] = ()
    #: Values of those parameters that still mean "this is the base tag".
    base_event_values: tuple[str, ...] = (
        "pageview",
        "page_view",
        "pagevisit",
        "page_visit",
        "",
    )
    id_format: str = ""
    setup_guidance: str = ""


MEDIA_PLATFORMS: dict[str, MediaPlatform] = {
    # ======================================================================
    # Advertising: majors
    # ======================================================================
    "meta": MediaPlatform(
        key="meta",
        label="Meta (Facebook) Pixel",
        # Confirmed live: gallery owner "facebook", repo
        # "GoogleTagManager-WebTemplate-For-FacebookPixel".
        gallery_markers=("facebook", "facebookincubator", "meta-pixel", "meta pixel"),
        # Confirmed live: the official template's required params are
        # `pixelId` and `advancedMatchingList`.
        id_parameters=("pixelId", "pixelID", "metaPixelId", "facebookPixelId"),
        init=(
            r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})['\"]",
            r"facebook\.com/tr\?[^\"'\s]*\bid=(\d{10,20})",
        ),
        events=(r"fbq\(\s*['\"]track(?:Custom|Single|SingleCustom)?['\"]",),
        name_keywords=("meta", "facebook", "fb "),
        event_parameters=("eventName", "standardEventName", "eecEventName"),
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
        label="TikTok Pixel",
        # Confirmed live: gallery owner "tiktok", repo "gtm-template-pixel".
        gallery_markers=("tiktok", "bytedance"),
        # Confirmed live: the official template uses snake_case `pixel_code`,
        # NOT `pixelCode`. It marks nothing required, so a tag with no pixel
        # code is accepted and silently sends nothing.
        id_parameters=("pixel_code", "pixelCode", "tiktokPixelCode"),
        init=(
            r"ttq\.load\(\s*['\"]([A-Za-z0-9]{15,25})['\"]",
            r"analytics\.tiktok\.com/i18n/pixel/events\.js\?sdkid=([A-Za-z0-9]{15,25})",
        ),
        events=(r"ttq\.(?:instance\([^)]*\)\.)?track\(",),
        name_keywords=("tiktok", "tt "),
        event_parameters=("event",),
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
        label="Pinterest Tag",
        # Confirmed live: gallery owner "pinterest", repo "ws-gtm-template".
        gallery_markers=("pinterest",),
        # Confirmed live: required params are `tagId` and `adeEventName`.
        # NOTE `tagId` collides with googtag and Microsoft UET, so this signal
        # is only meaningful alongside the gallery owner or a name match.
        id_parameters=("tagId", "pinterestTagId", "tid"),
        init=(
            r"pintrk\(\s*['\"]load['\"]\s*,\s*['\"](\d{10,16})['\"]",
            r"ct\.pinterest\.com/[^\"'\s]*\btid=(\d{10,16})",
        ),
        events=(r"pintrk\(\s*['\"]track['\"]",),
        name_keywords=("pinterest", "pintrk"),
        event_parameters=("eventName", "adeEventName"),
        id_format="13-digit numeric tag id",
        setup_guidance=(
            "Install the Pinterest Tag template from the gallery, or create a "
            "Custom HTML base tag with pintrk('load', '<TAG_ID>'); "
            "pintrk('page'); on Initialization - All Pages."
        ),
    ),
    "linkedin": MediaPlatform(
        key="linkedin",
        label="LinkedIn Insight Tag",
        gallery_markers=("linkedin",),
        id_parameters=("partnerId", "linkedInPartnerId", "partner_id"),
        init=(
            r"_linkedin_partner_id\s*=\s*['\"](\d{4,10})['\"]",
            r"_linkedin_data_partner_ids\.push\(\s*['\"](\d{4,10})['\"]",
            r"px\.ads\.linkedin\.com/collect/?\?[^\"'\s]*\bpid=(\d{4,10})",
        ),
        events=(r"lintrk\(\s*['\"]track['\"]",),
        name_keywords=("linkedin", "insight tag"),
        event_parameters=("conversionId",),
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
        label="Snap Pixel",
        gallery_markers=("snapchat", "snap-"),
        # Confirmed live: the gallery template uses `accountId` and
        # `eventName` -- not the `pixelId`/`eventType` a vendor-agnostic guess
        # would suggest. Template-derived hints override this.
        id_parameters=("accountId", "pixelId", "snapPixelId"),
        init=(
            r"snaptr\(\s*['\"]init['\"]\s*,\s*['\"]([^'\"]{6,64})['\"]",
            r"tr\.snapchat\.com/[^\"'\s]*\bpid=([^&\"'\s]+)",
        ),
        events=(r"snaptr\(\s*['\"]track['\"]",),
        name_keywords=("snapchat", "snap pixel"),
        event_parameters=("eventName", "eventType"),
        id_format="UUID-style pixel id",
        setup_guidance=(
            "Install the Snap Pixel template from the gallery, or create a "
            "Custom HTML base tag with snaptr('init', '<PIXEL_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    "microsoft_ads": MediaPlatform(
        key="microsoft_ads",
        label="Microsoft Advertising UET",
        gallery_markers=("microsoft advertising", "bing", "uet"),
        id_parameters=("tagId", "uetTagId", "ti"),
        init=(
            r"(?:^|[^A-Za-z])ti\s*:\s*['\"](\d{6,12})['\"]",
            r"bat\.bing\.com/action/0\?[^\"'\s]*\bti=(\d{6,12})",
        ),
        events=(r"uetq['\"]?\]?\.push\(\s*['\"]event['\"]",),
        name_keywords=("microsoft advertising", "bing", "uet"),
        event_parameters=("eventAction", "eventCategory", "eventLabel"),
        id_format="8-9 digit numeric UET tag id",
        setup_guidance=(
            "Install the Microsoft Advertising UET template from the gallery, "
            "or create a Custom HTML base tag with the UET snippet on "
            "Initialization - All Pages."
        ),
    ),
    "x_twitter": MediaPlatform(
        key="x_twitter",
        label="X (Twitter) Pixel",
        gallery_markers=("twitter", "x-corp"),
        id_parameters=("pixelId", "twitterPixelId"),
        init=(
            r"twq\(\s*['\"](?:config|init)['\"]\s*,\s*['\"]([A-Za-z0-9]{4,12})['\"]",
            r"analytics\.twitter\.com/[^\"'\s]*\btxn_id=([A-Za-z0-9]{4,12})",
        ),
        events=(r"twq\(\s*['\"]event['\"]",),
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
        label="Reddit Pixel",
        gallery_markers=("reddit",),
        # Confirmed live: required param is `id`, event is `eventType`.
        id_parameters=("id", "advertiserId", "redditPixelId"),
        init=(r"rdt\(\s*['\"]init['\"]\s*,\s*['\"](t2_[A-Za-z0-9]+)['\"]",),
        events=(r"rdt\(\s*['\"]track['\"]",),
        name_keywords=("reddit", "rdt"),
        event_parameters=("eventType", "customEventName"),
        id_format="advertiser id starting with t2_",
        setup_guidance=(
            "Install the Reddit Pixel template from the gallery, or create a "
            "Custom HTML base tag with rdt('init', '<ADVERTISER_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    "criteo": MediaPlatform(
        key="criteo",
        label="Criteo OneTag",
        gallery_markers=("criteo",),
        # Confirmed live: the Criteo Loader template uses `partnerId` and
        # declares no event parameter at all, which is what marks it a loader.
        id_parameters=("partnerId", "accountId", "caccount", "criteoAccountId"),
        init=(
            r"['\"]?caccount['\"]?\s*[:=]\s*['\"]?(\d{4,8})",
            r"setAccount['\"]?\s*,?\s*['\"]?account['\"]?\s*:\s*['\"]?(\d{4,8})",
            r"static\.criteo\.net/[^\"'\s]*\ba=(\d{4,8})",
        ),
        # `criteo_q.push(` is not an event marker: the loader pushes too. Only
        # a named event distinguishes them.
        events=(
            r"\{\s*['\"]?event['\"]?\s*:\s*['\"](?:viewItem|viewList|viewBasket"
            r"|trackTransaction|viewSearch)['\"]",
        ),
        events_repeat_the_id=True,
        name_keywords=("criteo",),
        event_parameters=("eventType",),
        id_format="5-6 digit numeric account id",
        setup_guidance=(
            "Install the Criteo OneTag template from the gallery, or create a "
            "Custom HTML base tag loading ld.js with the account id."
        ),
    ),
    # ======================================================================
    # Advertising: native, programmatic and retail media
    # ======================================================================
    "taboola": MediaPlatform(
        key="taboola",
        label="Taboola Pixel",
        gallery_markers=("taboola",),
        id_parameters=("accountId", "taboolaAccountId", "tfaId"),
        init=(
            r"cdn\.taboola\.com/libtrc/unip/(\d{4,10})/tfa\.js",
            r"_tfa\.push\(\s*\{[^}]*\bid\s*:\s*(\d{4,10})",
        ),
        # The base snippet pushes `name: 'page_view'` itself, so only a name
        # that is NOT a page view marks an event tag.
        events=(r"_tfa\.push\(\s*\{[^}]*\bname\s*:\s*['\"](?!page_?view)",),
        # Taboola repeats `id:` in every event push.
        events_repeat_the_id=True,
        name_keywords=("taboola",),
        event_parameters=("name", "eventName"),
        id_format="numeric account id",
        setup_guidance=(
            "Install the Taboola Pixel template from the gallery, or create a "
            "Custom HTML base tag loading libtrc/unip/<ACCOUNT_ID>/tfa.js on "
            "Initialization - All Pages."
        ),
    ),
    "outbrain": MediaPlatform(
        key="outbrain",
        label="Outbrain Pixel",
        gallery_markers=("outbrain",),
        id_parameters=("marketerId", "advertiserId", "obMarketerId"),
        init=(
            r"obApi\(\s*['\"](?:init|marketerId)['\"]\s*,\s*['\"]([A-Za-z0-9]+)['\"]",
            r"amplifyPixel\(\s*['\"]([A-Za-z0-9]+)['\"]",
        ),
        events=(r"obApi\(\s*['\"]track['\"]",),
        name_keywords=("outbrain", "obapi", "amplify"),
        event_parameters=("eventName",),
        id_format="alphanumeric marketer id",
        setup_guidance=(
            "Install the Outbrain Pixel template from the gallery, or create a "
            "Custom HTML base tag with obApi('init', '<MARKETER_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    "adroll": MediaPlatform(
        key="adroll",
        label="AdRoll",
        gallery_markers=("adroll", "nextroll"),
        id_parameters=("adv_id", "advId", "adrollAdvId", "pix_id", "pixId"),
        init=(
            r"adroll_adv_id\s*=\s*['\"]([A-Za-z0-9]+)['\"]",
            r"adroll_pix_id\s*=\s*['\"]([A-Za-z0-9]+)['\"]",
        ),
        events=(r"adroll_segments\s*=", r"__adroll\.record_adroll_email\("),
        events_repeat_the_id=True,
        name_keywords=("adroll", "nextroll"),
        event_parameters=("segmentName", "eventName"),
        id_format="22-character advertiser id",
        setup_guidance=(
            "Install the AdRoll template from the gallery, or create a Custom "
            "HTML base tag setting adroll_adv_id and adroll_pix_id on "
            "Initialization - All Pages."
        ),
    ),
    "quora": MediaPlatform(
        key="quora",
        label="Quora Pixel",
        gallery_markers=("quora",),
        id_parameters=("pixelId", "quoraPixelId"),
        init=(r"qp\(\s*['\"]init['\"]\s*,\s*['\"]([a-f0-9]{16,40})['\"]",),
        events=(r"qp\(\s*['\"]track['\"]",),
        name_keywords=("quora",),
        event_parameters=("eventName",),
        id_format="32-character hexadecimal pixel id",
        setup_guidance=(
            "Install the Quora Pixel template from the gallery, or create a "
            "Custom HTML base tag with qp('init', '<PIXEL_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    "amazon_ads": MediaPlatform(
        key="amazon_ads",
        label="Amazon Ads",
        gallery_markers=("amazon",),
        id_parameters=("tagId", "amazonTagId", "pixelId"),
        init=(
            r"amzn\(\s*['\"]addTag['\"]\s*,\s*['\"]([A-Za-z0-9-]{8,})['\"]",
            r"s\.amazon-adsystem\.com/iu3\?[^\"'\s]*\bpid=([A-Za-z0-9]+)",
        ),
        events=(r"amzn\(\s*['\"]trackEvent['\"]",),
        name_keywords=("amazon",),
        event_parameters=("eventName",),
        id_format="UUID-style tag id",
        setup_guidance=(
            "Install the Amazon Ads template from the gallery, or create a "
            "Custom HTML base tag calling amzn('setRegion', ...) on "
            "Initialization - All Pages."
        ),
    ),
    "adform": MediaPlatform(
        key="adform",
        label="Adform",
        gallery_markers=("adform",),
        id_parameters=("clientId", "trackingId", "pagename", "adformClientId"),
        init=(
            r"pm\(\s*['\"]setup['\"]\s*,\s*['\"](\d{4,10})['\"]",
            r"_adftrack\s*=[^;]*?\bpm\s*:\s*['\"]?(\d{4,10})",
        ),
        events=(r"pm\(\s*['\"]track['\"]",),
        name_keywords=("adform",),
        event_parameters=("eventName", "pagename"),
        id_format="numeric client id",
        setup_guidance=(
            "Install the Adform template from the gallery, or create a Custom "
            "HTML base tag with pm('setup', '<CLIENT_ID>') on Initialization - "
            "All Pages."
        ),
    ),
    "rtb_house": MediaPlatform(
        key="rtb_house",
        label="RTB House",
        gallery_markers=("rtb house", "rtbhouse", "creativecdn"),
        id_parameters=("hashId", "advertiserHash", "tagId"),
        init=(r"tags\.creativecdn\.com/([A-Za-z0-9_-]{6,})\.js",),
        name_keywords=("rtb house", "rtbhouse"),
        event_parameters=("eventType", "eventName"),
        id_format="advertiser hash",
        setup_guidance=(
            "Install the RTB House template from the gallery, or create a "
            "Custom HTML base tag loading tags.creativecdn.com/<HASH>.js on "
            "Initialization - All Pages."
        ),
    ),
    "teads": MediaPlatform(
        key="teads",
        label="Teads",
        gallery_markers=("teads",),
        id_parameters=("pixelId", "teadsPixelId", "pid"),
        init=(
            r"analytics_tag_id\s*[:=]\s*['\"](\d{4,10})['\"]",
            r"teads\.tv[^\"'\s]*\b(?:pid|analytics_tag_id)=(\d{4,10})",
        ),
        name_keywords=("teads",),
        event_parameters=("eventName", "conversionType"),
        id_format="numeric analytics tag id",
        setup_guidance=(
            "Install the Teads template from the gallery, or create a Custom "
            "HTML base tag loading the Teads pixel on Initialization - All "
            "Pages."
        ),
    ),
    # ======================================================================
    # Affiliate networks -- self-contained conversion tags, no base tag
    # ======================================================================
    "awin": MediaPlatform(
        key="awin",
        label="Awin",
        event_model="standalone",
        gallery_markers=("awin", "affiliate window"),
        id_parameters=("advertiserId", "awinAdvertiserId", "merchantId"),
        init=(
            r"dwin1\.com/(\d{3,8})\.js",
            r"AWIN\.Tracking\.Sale[^;]*?advertiserId\s*=\s*['\"]?(\d{3,8})",
        ),
        name_keywords=("awin", "affiliate window"),
        id_format="numeric advertiser id",
        setup_guidance=(
            "Awin sale tags are self-contained: each carries the advertiser id "
            "and the order details. No separate base tag is required, though "
            "the MasterTag (dwin1.com/<ID>.js) is usually present site-wide."
        ),
    ),
    "rakuten": MediaPlatform(
        key="rakuten",
        label="Rakuten Advertising",
        event_model="standalone",
        gallery_markers=("rakuten", "linkshare"),
        id_parameters=("merchantId", "mid", "rakutenMerchantId"),
        init=(r"tag\.rmp\.rakuten\.com/(\d{4,10})\.ct\.js",),
        name_keywords=("rakuten", "linkshare"),
        id_format="numeric merchant id",
        setup_guidance=(
            "Rakuten conversion tags carry the merchant id themselves. No "
            "separate base tag is required."
        ),
    ),
    "impact": MediaPlatform(
        key="impact",
        label="Impact",
        event_model="standalone",
        gallery_markers=("impactradius", "impact.com", "impact "),
        id_parameters=("accountId", "campaignId", "universalTrackingTag"),
        init=(r"utt\.impactcdn\.com/(A\d{5,}[A-Za-z0-9-]*)\.js",),
        name_keywords=("impact radius", "impactradius"),
        id_format="Universal Tracking Tag id (starts with A)",
        setup_guidance=(
            "Impact's Universal Tracking Tag loads site-wide and its "
            "conversion tags carry their own identifiers."
        ),
    ),
    # ======================================================================
    # Regional advertising
    # ======================================================================
    "yandex_metrica": MediaPlatform(
        key="yandex_metrica",
        label="Yandex Metrica",
        gallery_markers=("yandex",),
        id_parameters=("counterId", "id", "yandexCounterId"),
        init=(
            r"ym\(\s*(\d{6,10})\s*,\s*['\"]init['\"]",
            r"mc\.yandex\.ru/watch/(\d{6,10})",
        ),
        events=(r"ym\(\s*\d+\s*,\s*['\"](?:reachGoal|hit|params)['\"]",),
        name_keywords=("yandex", "metrica", "metrika"),
        event_parameters=("goalName", "eventName"),
        id_format="8-9 digit numeric counter id",
        setup_guidance=(
            "Install the Yandex Metrica template from the gallery, or create a "
            "Custom HTML base tag with ym(<COUNTER_ID>, 'init', {...}) on "
            "Initialization - All Pages."
        ),
    ),
    "line": MediaPlatform(
        key="line",
        label="LINE Tag",
        # "line" alone is a substring of "linkedin" and of half the English
        # language, so every marker here is qualified.
        gallery_markers=("line tag", "line ads", "linecorp"),
        id_parameters=("tagId", "lineTagId"),
        init=(r"_lt\(\s*['\"]init['\"][^)]*tagId\s*:\s*['\"]([A-Za-z0-9-]+)['\"]",),
        events=(r"_lt\(\s*['\"]send['\"]",),
        name_keywords=("line tag", "line ads"),
        event_parameters=("eventName", "customEventName"),
        id_format="hyphenated alphanumeric tag id",
        setup_guidance=(
            "Install the LINE Tag template from the gallery, or create a "
            "Custom HTML base tag with _lt('init', {tagId: '<TAG_ID>'}) on "
            "Initialization - All Pages."
        ),
    ),
    "kakao": MediaPlatform(
        key="kakao",
        label="Kakao Pixel",
        gallery_markers=("kakao",),
        id_parameters=("trackId", "kakaoTrackId"),
        # Kakao repeats the track id in every call -- `kakaoPixel(id).purchase()`
        # -- so only the `.pageView()` call counts as the installation.
        init=(r"kakaoPixel\(\s*['\"](\d{6,20})['\"]\s*\)\s*\.\s*pageView\(",),
        events=(
            r"kakaoPixel\(\s*['\"]\d{6,20}['\"]\s*\)\s*\.\s*"
            r"(?:completeRegistration|search|viewContent|addToCart|purchase|signUp)\(",
        ),
        events_repeat_the_id=True,
        name_keywords=("kakao",),
        event_parameters=("eventName",),
        id_format="13-digit numeric track id",
        setup_guidance=(
            "Install the Kakao Pixel template from the gallery, or create a "
            "Custom HTML base tag loading kp.js and calling "
            "kakaoPixel('<TRACK_ID>').pageView() on Initialization - All Pages."
        ),
    ),
    "naver": MediaPlatform(
        key="naver",
        label="Naver Common Tag",
        gallery_markers=("naver",),
        id_parameters=("accountId", "naverAccountId", "wa"),
        init=(r"wcs_add\s*\[\s*['\"]wa['\"]\s*\]\s*=\s*['\"]([A-Za-z0-9_]+)['\"]",),
        # A Naver conversion tag re-declares wcs_add['wa'], so the presence of
        # wcs.trans() is what tells the two apart.
        events=(r"wcs\.trans\(",),
        events_repeat_the_id=True,
        name_keywords=("naver", "wcs"),
        event_parameters=("eventName",),
        id_format="account id starting with s_",
        setup_guidance=(
            "Install the Naver Common Tag template from the gallery, or create "
            "a Custom HTML base tag setting wcs_add['wa'] and calling wcs_do() "
            "on Initialization - All Pages."
        ),
    ),
    "vk": MediaPlatform(
        key="vk",
        label="VK Pixel",
        gallery_markers=("vkontakte", "vk pixel", "vk-pixel"),
        id_parameters=("pixelId", "vkPixelId", "priceListId"),
        init=(r"VK\.Retargeting\.Init\(\s*['\"]([A-Za-z0-9-]+)['\"]",),
        events=(r"VK\.Goal\(",),
        events_repeat_the_id=True,
        name_keywords=("vkontakte", "vk pixel"),
        event_parameters=("eventName", "goal"),
        id_format="pixel id starting with VK-RTRG-",
        setup_guidance=(
            "Install the VK Pixel template from the gallery, or create a "
            "Custom HTML base tag with VK.Retargeting.Init('<PIXEL_ID>') on "
            "Initialization - All Pages."
        ),
    ),
    # ======================================================================
    # Analytics, CRM and marketing automation
    # ======================================================================
    "hubspot": MediaPlatform(
        key="hubspot",
        label="HubSpot",
        gallery_markers=("hubspot",),
        id_parameters=("portalId", "hubId", "hubspotPortalId"),
        init=(
            r"js\.hs-scripts\.com/(\d{4,12})\.js",
            r"js\.hsforms\.net[^\"'\s]*portalId\D*(\d{4,12})",
        ),
        events=(r"_hsq\.push\(\s*\[\s*['\"](?:trackEvent|identify|trackPageView)['\"]",),
        name_keywords=("hubspot",),
        event_parameters=("eventName", "eventId"),
        id_format="numeric portal (hub) id",
        setup_guidance=(
            "Install the HubSpot template from the gallery, or create a Custom "
            "HTML base tag loading js.hs-scripts.com/<PORTAL_ID>.js on "
            "Initialization - All Pages."
        ),
    ),
    "klaviyo": MediaPlatform(
        key="klaviyo",
        label="Klaviyo",
        gallery_markers=("klaviyo",),
        id_parameters=("companyId", "publicApiKey", "klaviyoCompanyId"),
        init=(
            r"static\.klaviyo\.com/onsite/js/klaviyo\.js\?company_id=([A-Za-z0-9]{4,12})",
            r"klaviyo\.init\(\s*\{[^}]*account\s*:\s*['\"]([A-Za-z0-9]{4,12})['\"]",
        ),
        events=(r"_learnq\.push\(\s*\[\s*['\"](?:track|identify)['\"]",),
        name_keywords=("klaviyo",),
        event_parameters=("eventName", "metric"),
        id_format="6-character public API key (company id)",
        setup_guidance=(
            "Install the Klaviyo template from the gallery, or create a Custom "
            "HTML base tag loading klaviyo.js?company_id=<PUBLIC_API_KEY> on "
            "Initialization - All Pages."
        ),
    ),
    "segment": MediaPlatform(
        key="segment",
        label="Segment",
        gallery_markers=("segment",),
        id_parameters=("writeKey", "segmentWriteKey"),
        init=(r"analytics\.load\(\s*['\"]([A-Za-z0-9]{16,40})['\"]",),
        events=(r"analytics\.(?:track|identify|page)\(",),
        name_keywords=("segment",),
        event_parameters=("eventName",),
        id_format="write key",
        setup_guidance=(
            "Install the Segment template from the gallery, or create a Custom "
            "HTML base tag calling analytics.load('<WRITE_KEY>') on "
            "Initialization - All Pages."
        ),
    ),
    "mixpanel": MediaPlatform(
        key="mixpanel",
        label="Mixpanel",
        gallery_markers=("mixpanel",),
        id_parameters=("token", "projectToken", "mixpanelToken"),
        init=(r"mixpanel\.init\(\s*['\"]([a-f0-9]{16,40})['\"]",),
        events=(r"mixpanel\.(?:track|identify|people)\b",),
        name_keywords=("mixpanel",),
        event_parameters=("eventName",),
        id_format="32-character hexadecimal project token",
        setup_guidance=(
            "Install the Mixpanel template from the gallery, or create a "
            "Custom HTML base tag calling mixpanel.init('<TOKEN>') on "
            "Initialization - All Pages."
        ),
    ),
    "amplitude": MediaPlatform(
        key="amplitude",
        label="Amplitude",
        gallery_markers=("amplitude",),
        id_parameters=("apiKey", "amplitudeApiKey"),
        init=(
            r"amplitude(?:\.getInstance\(\))?\.init\(\s*['\"]([a-f0-9]{16,40})['\"]",
        ),
        events=(r"amplitude[^;]*\.(?:logEvent|track)\(",),
        name_keywords=("amplitude",),
        event_parameters=("eventName", "eventType"),
        id_format="32-character hexadecimal API key",
        setup_guidance=(
            "Install the Amplitude template from the gallery, or create a "
            "Custom HTML base tag calling amplitude.init('<API_KEY>') on "
            "Initialization - All Pages."
        ),
    ),
    # ======================================================================
    # Experience: one install tag, no event tags
    # ======================================================================
    "hotjar": MediaPlatform(
        key="hotjar",
        label="Hotjar",
        event_model="single",
        gallery_markers=("hotjar",),
        id_parameters=("siteId", "hjid", "hotjarSiteId"),
        init=(
            r"hjid\s*:\s*(\d{4,10})",
            r"static\.hotjar\.com/c/hotjar-(\d{4,10})\.js",
        ),
        name_keywords=("hotjar",),
        id_format="numeric site id",
        setup_guidance=(
            "Hotjar is a single install tag on Initialization - All Pages. "
            "Install the template from the gallery or use the Custom HTML "
            "snippet with your site id."
        ),
    ),
    "clarity": MediaPlatform(
        key="clarity",
        label="Microsoft Clarity",
        event_model="single",
        gallery_markers=("clarity",),
        id_parameters=("projectId", "clarityProjectId"),
        init=(r"clarity\.ms/tag/([A-Za-z0-9]{6,20})",),
        name_keywords=("clarity",),
        id_format="10-character project id",
        setup_guidance=(
            "Clarity is a single install tag on Initialization - All Pages, "
            "loading clarity.ms/tag/<PROJECT_ID>."
        ),
    ),
    "crazy_egg": MediaPlatform(
        key="crazy_egg",
        label="Crazy Egg",
        event_model="single",
        gallery_markers=("crazy egg", "crazyegg"),
        id_parameters=("accountNumber", "crazyEggId"),
        init=(r"script\.crazyegg\.com/pages/scripts/(\d{2,6}/\d{2,6})\.js",),
        name_keywords=("crazy egg", "crazyegg"),
        id_format="8-digit account number, split across the script path",
        setup_guidance=(
            "Crazy Egg is a single install tag on Initialization - All Pages."
        ),
    ),
    "lucky_orange": MediaPlatform(
        key="lucky_orange",
        label="Lucky Orange",
        event_model="single",
        gallery_markers=("lucky orange", "luckyorange"),
        id_parameters=("siteId", "luckyOrangeSiteId"),
        init=(r"tools\.luckyorange\.com/core/lo\.js\?site-id=([A-Za-z0-9]+)",),
        name_keywords=("lucky orange", "luckyorange"),
        id_format="alphanumeric site id",
        setup_guidance=(
            "Lucky Orange is a single install tag on Initialization - All Pages."
        ),
    ),
    "intercom": MediaPlatform(
        key="intercom",
        label="Intercom",
        event_model="single",
        gallery_markers=("intercom",),
        id_parameters=("appId", "app_id", "intercomAppId"),
        # `app_id` on its own appears in several unrelated snippets, so both
        # patterns require an Intercom-specific anchor.
        init=(
            r"intercomSettings\s*=\s*\{[^}]*app_id\s*:\s*['\"]([a-z0-9]{6,12})['\"]",
            r"widget\.intercom\.io/widget/([a-z0-9]{6,12})",
        ),
        name_keywords=("intercom",),
        id_format="8-character app id",
        setup_guidance=(
            "Intercom is a single install tag; the messenger is booted once "
            "per page with your app id."
        ),
    ),
}


#: GTM ships built-in tag types for a few third-party vendors, alongside the
#: community templates. They are neither `cvt_` nor Custom HTML, so nothing in
#: the gallery-marker or snippet machinery sees them: a container's two
#: LinkedIn Insight tags were invisible to the audit while its two hand-written
#: ones were found, which reads as the model having missed them.
#:
#: `bzi` is confirmed against a live container -- its only parameter is `id`,
#: holding the partner id. The rest are GTM's documented built-ins; an entry
#: for a type that does not exist simply never matches, so listing them costs
#: nothing and closes the gap wherever they do.
#:
#: **This list does not have to be complete, and never will be.** GTM ships
#: built-in types for vendors that come and go, and this project runs in
#: containers nobody here has seen. `tag_identity.is_unrecognised_vendor_type`
#: catches every type not named here by structure rather than by name -- not
#: Google's own, not a `cvt_` template, not hand-written script -- so such a
#: tag is still read as a base tag, still compared with others of its type, and
#: still listed in the account inventory. What an entry below adds is the
#: vendor's NAME: a friendly label, the setup guidance, and inclusion in the
#: prerequisite check. Nothing about duplicate detection depends on it.
NATIVE_MEDIA_TYPES: dict[str, str] = {
    "bzi": "linkedin",
    "twitter_website_tag": "x_twitter",
    "pntr": "pinterest",
    "crto": "criteo",
    "hjtc": "hotjar",
}


def ambiguous_id_parameters() -> set[str]:
    """Parameter names too generic to identify a platform on their own.

    `tagId` belongs to Pinterest, to Microsoft UET *and* to Google's own
    `googtag`. Treating it as evidence made a container with one Google Tag and
    one Pinterest tag report duplicate base pixels for two platforms that were
    not there. A name is ambiguous when more than one platform claims it, or
    when a native Google tag type already uses it.

    Computed rather than hardcoded so that adding a platform cannot silently
    reintroduce the collision -- with 35 platforms registered, `accountId` and
    `pixelId` are claimed by several and now correctly prove nothing.
    """
    from collections import Counter

    from .tag_specs import TAG_SPECS

    counts = Counter(
        name for platform in MEDIA_PLATFORMS.values() for name in platform.id_parameters
    )
    shared = {name for name, total in counts.items() if total > 1}
    native = {key for spec in TAG_SPECS.values() for key in spec.known}
    return shared | (native & set(counts))
