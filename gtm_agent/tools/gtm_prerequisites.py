"""Whether the container has the foundation a tag depends on.

Split out of `gtm_read` because it answers a different question. Those tools
report what is in the container; these decide whether what is in it is
*enough* -- a GA4 event needs a Google Tag with a `G-` destination, a Google
Ads conversion needs a Conversion Linker, a TikTok event needs `ttq.load()` to
have run. That judgement is the largest single body of rules in the project and
it was buried at the end of a 1500-line module of listing tools.

The dependency runs one way: this module reads `gtm_read` for the reserved
built-in trigger ids and never the reverse.
"""

from __future__ import annotations

import re

from typing import Any
from typing import Optional

from ..config import settings
from .gtm_client import paginate
from .gtm_client import parameters_to_dict
from .gtm_client import scalar_values
from .gtm_client import setting_values
from .gtm_client import tool_errors
from .gtm_client import workspaces
from .gtm_read import BUILT_IN_TRIGGERS
from .gtm_templates import index_templates
from .gtm_templates import resolve_tag_type
from .gtm_templates import template_bootstraps_library
from .media_platforms import MEDIA_PLATFORMS
from .media_platforms import NATIVE_MEDIA_TYPES
from .media_platforms import ambiguous_id_parameters
from .tag_specs import TAG_SPECS
from .vendor_snippets import event_signal
from .vendor_snippets import init_signal


#: Tag types that act as the base ("foundation") layer of a container.
BASE_TAG_TYPES = {
    "googtag": "Google Tag",
    "gaawc": "Google Analytics: GA4 Configuration (legacy)",
    "gclidw": "Conversion Linker",
}

#: A Google Tag's destination is encoded in the prefix of its `tagId`. A tag
#: pointing at GA4 does nothing for Google Ads, so "is there a Google Tag?" is
#: never the right question -- "is there one for THIS destination?" is.
GOOGLE_TAG_DESTINATIONS = {
    "G-": "Google Analytics 4",
    "AW-": "Google Ads",
    "DC-": "Floodlight / Campaign Manager 360",
    "GT-": "Google Tag container (destinations configured outside GTM)",
}

#: `GT-` routes to destinations chosen in the Google Tag interface, which the
#: container cannot see. Its presence neither proves nor disproves coverage.
_OPAQUE_DESTINATION_PREFIX = "GT-"


def google_tag_destination(tag: dict[str, Any]) -> Optional[str]:
    """Return the destination id a base tag points at, if it declares one."""
    flat = parameters_to_dict(tag.get("parameter"))
    value = flat.get("tagId") or flat.get("measurementId")
    return str(value).strip() if value else None


def _destination_matches(tag: dict[str, Any], prefixes: tuple[str, ...]) -> bool:
    destination = google_tag_destination(tag)
    if not destination:
        return False
    return any(destination.upper().startswith(p) for p in prefixes)


def evaluate_consent_initialization(
    tags: list[dict[str, Any]], triggers: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check whether anything actually initializes Consent Mode.

    Consent Initialization is a RESERVED trigger. `triggers().list()` never
    returns it, so looking for a trigger whose type is `consentInit` reports
    "missing" in every container, including correctly configured ones. What
    proves consent is initialized is a TAG firing on the reserved id.

    Kept free of API calls so the rule can be tested directly.
    """
    consent_trigger_id = next(
        tid for tid, meta in BUILT_IN_TRIGGERS.items() if meta["type"] == "consentInit"
    )
    custom = [t for t in triggers if t.get("type") == "consentInit"]
    accepted = {consent_trigger_id} | {str(t.get("triggerId")) for t in custom}

    firing = [
        t
        for t in tags
        if not t.get("paused")
        and accepted & {str(i) for i in (t.get("firingTriggerId") or [])}
    ]

    return {
        "status": "present" if firing else "missing",
        "consent_trigger_id": consent_trigger_id,
        "tags": firing,
        "remedy": None
        if firing
        else (
            "Fire the CMP / Consent Mode default tag on Consent Initialization - "
            f"All Pages (trigger id {consent_trigger_id}). A CMP on All Pages "
            "(2147479553) runs too late: measurement tags may already have "
            "fired before the default consent state is set."
        ),
    }


def evaluate_requirement(
    requirement: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Decide whether one foundation requirement is satisfied.

    Kept free of API calls so the destination rules can be tested directly.

    The subtlety is `destination_prefixes`. "Is there a Google Tag?" is the
    wrong question: a `googtag` pointing at `G-` does nothing for Google Ads,
    and a container that has one is routinely assumed to cover both. A `GT-`
    container id is a third case -- its destinations are chosen in the Google
    Tag interface, which this container cannot see, so the honest answer is
    "uncertain" rather than present or missing.

    Returns:
        `status`, the matching tags, the ones pointing elsewhere, any opaque
        `GT-` tags, and a note explaining the destination mismatch.
    """
    prefixes = requirement.get("destination_prefixes")

    wrong_destination: list[dict[str, Any]] = []
    opaque: list[dict[str, Any]] = []
    if prefixes:
        matches = []
        for tag in candidates:
            destination = google_tag_destination(tag)
            if destination and destination.upper().startswith(
                _OPAQUE_DESTINATION_PREFIX
            ):
                opaque.append(tag)
            elif _destination_matches(tag, prefixes):
                matches.append(tag)
            else:
                wrong_destination.append(tag)
    else:
        matches = list(candidates)

    active = [t for t in matches if not t.get("paused")]
    with_trigger = [t for t in active if t.get("firingTriggerId")]
    active_opaque = [t for t in opaque if not t.get("paused")]

    if with_trigger:
        status = "present"
    elif active:
        status = "present_but_never_fires"
    elif matches:
        status = "present_but_paused"
    elif active_opaque:
        status = "uncertain"
    else:
        status = "missing"

    destination_note = None
    if prefixes:
        wanted = " or ".join(p for p in prefixes if p != _OPAQUE_DESTINATION_PREFIX)
        if status == "uncertain":
            ids = [google_tag_destination(t) for t in active_opaque]
            destination_note = (
                f"Found a Google Tag container id ({', '.join(i for i in ids if i)}). "
                "Its destinations are configured in the Google Tag interface, "
                "not in this container, so it may or may not cover "
                f"{wanted}. Ask the user to confirm."
            )
        elif status == "missing" and wrong_destination:
            destination_note = (
                f"{len(wrong_destination)} Google Tag(s) exist but none targets "
                f"{wanted}: "
                + ", ".join(
                    f"{t.get('name')} -> {google_tag_destination(t)}"
                    for t in wrong_destination
                )
                + ". A Google Tag for one destination does nothing for another."
            )

    return {
        "status": status,
        "matches": matches,
        "opaque": active_opaque,
        "wrong_destination": wrong_destination,
        "destination_note": destination_note,
    }


#: Which foundation each product depends on.
_PRODUCT_REQUIREMENTS: dict[str, list[dict[str, Any]]] = {
    "ga4": [
        {
            "requirement": "base_google_tag",
            "label": "Google Tag with a GA4 (G-) destination",
            "tag_types": ["googtag", "gaawc"],
            "destination_prefixes": ("G-", "GT-"),
            "severity": "blocking",
            "why": (
                "A GA4 Event tag (gaawe) has no measurement context of its own. "
                "Without a Google Tag loaded first, the event either does not "
                "fire or lands on an undocumented on-page gtag snippet that the "
                "container does not manage."
            ),
            "remedy": (
                'create_tag(name="Google Tag - GA4", tag_type="googtag", '
                'parameters_json=\'{"tagId": "{{CONST - GA4 Measurement ID}}"}\', '
                "firing_trigger_ids=[\"2147479553\"])  # 2147479553 = All Pages"
            ),
        }
    ],
    "google_ads": [
        {
            "requirement": "conversion_linker",
            "label": "Conversion Linker",
            "tag_types": ["gclidw"],
            "severity": "blocking",
            "why": (
                "Without a Conversion Linker storing gclid/wbraid in a "
                "first-party cookie, Google Ads cannot attribute the conversion."
            ),
            "remedy": (
                'create_tag(name="Google Ads - Conversion Linker", '
                'tag_type="gclidw", firing_trigger_ids=["2147479553"])'
            ),
        },
        {
            "requirement": "base_google_tag",
            "label": "Google Tag with a Google Ads (AW-) destination",
            "tag_types": ["googtag"],
            "destination_prefixes": ("AW-", "GT-"),
            "severity": "high",
            "why": (
                "A Google Tag carrying the AW- id is what enables enhanced "
                "conversions, remarketing audiences and cross-device "
                "attribution. A conversion tag alone still records the "
                "conversion, so this is not fatal -- but a Google Tag pointing "
                "at GA4 (G-) does nothing for Google Ads, and having one is "
                "commonly mistaken for having both."
            ),
            "remedy": (
                'create_tag(name="Google Tag - Google Ads", tag_type="googtag", '
                'parameters_json=\'{"tagId": "{{CONST - Google Ads Conversion ID}}"}\', '
                'firing_trigger_ids=["2147479553"])'
            ),
        },
    ],
    "floodlight": [
        {
            "requirement": "conversion_linker",
            "label": "Conversion Linker",
            "tag_types": ["gclidw"],
            "severity": "blocking",
            "why": (
                "Floodlight relies on the Conversion Linker for attribution in "
                "browsers that restrict third-party cookies."
            ),
            "remedy": (
                'create_tag(name="Google Ads - Conversion Linker", '
                'tag_type="gclidw", firing_trigger_ids=["2147479553"])'
            ),
        },
        {
            "requirement": "base_google_tag",
            "label": "Google Tag with a Floodlight (DC-) destination",
            "tag_types": ["googtag"],
            "destination_prefixes": ("DC-", "GT-"),
            "severity": "recommended",
            "why": (
                "Floodlight activities can be served through a Google Tag with "
                "a DC- destination instead of individual flc/fls tags, which "
                "gives consent handling and first-party cookies for free. "
                "Optional when dedicated Floodlight tags are already in place."
            ),
            "remedy": (
                'create_tag(name="Google Tag - Floodlight", tag_type="googtag", '
                "parameters_json='{\"tagId\": \"{{CONST - Floodlight DC ID}}\"}' "
                'firing_trigger_ids=["2147479573"])'
            ),
        },
    ],
}

#: Tag types that depend on a foundation, mapped to the product that owns it.
DEPENDENT_TAG_TYPES = {
    "gaawe": "ga4",
    "awct": "google_ads",
    "sp": "google_ads",
    "flc": "floodlight",
    "fls": "floodlight",
}


def _base_tag_identifier(tag: dict[str, Any]) -> Optional[str]:
    """Pull the measurement / destination id out of a base tag."""
    flat = parameters_to_dict(tag.get("parameter"))
    return flat.get("tagId") or flat.get("measurementId") or None


#: Tag types Google defines natively. A third-party pixel is never one of
#: these, so they must be excluded from media matching entirely -- `googtag`
#: declares `tagId`, which Pinterest and Microsoft UET also use, and without
#: this exclusion one Google Tag reads as a base pixel for both.
#: `html` and `img` stay in scope: they legitimately host third-party pixels.
_NATIVE_TAG_TYPES = set(TAG_SPECS) - {"html", "img"}


def _classify_media_role(
    platform,
    flat: dict[str, Any],
    name: str,
    base_marker,
    event_marker,
    hints: Optional[dict[str, Any]] = None,
) -> str:
    """Decide whether a tag is the platform's setup tag, an event tag, or unclear.

    When the tag comes from an installed template, the template's own parameter
    contract decides. Hardcoded per-vendor names do not survive contact with
    reality -- Snapchat calls its event `eventName`, Reddit `eventType`,
    Pinterest declares both `eventName` and `adeEventName`, and Criteo's loader
    declares no event at all. `hints` comes from `template_role_hints`, which
    reads that from the template; the registry is only the fallback for Custom
    HTML tags, where there is no template to read.

    Returns "setup", "event" or "unclear". Guessing "setup" when unsure is what
    made every Pinterest purchase tag look like a duplicate base pixel, so the
    unclear case stays unclear.
    """
    if event_marker and not base_marker:
        return "event"
    if base_marker:
        return "setup"

    if hints is not None and hints["parameter_count"]:
        # A template that declares parameters but no event parameter can only
        # produce base tags -- this is what identifies a loader template such as
        # Criteo's. A template we could not parse declares nothing, and proves
        # nothing, so it must not take this branch.
        if not hints["declares_events"]:
            return "setup"
        event_parameters = hints["event_parameters"]
    else:
        event_parameters = list(platform.event_parameters)

    # A tag that sets the event to a page view IS the base tag; one that sets
    # it to anything else is an event tag. Only an unset event is ambiguous.
    readable = {**setting_values(flat), **flat}
    for param in event_parameters:
        value = readable.get(param)
        if value is None:
            continue
        if str(value).strip().lower() in platform.base_event_values:
            return "setup"
        return "event"

    if any(keyword in name for keyword in platform.base_keywords):
        return "setup"
    if "event" in name or "conversion" in name:
        return "event"
    return "unclear"


def classify_media_role_for_tag(
    tag: dict[str, Any],
    platform_by_type: dict[str, str],
    template_hints: dict[str, dict[str, Any]],
) -> str:
    """Public wrapper: is this template tag a setup tag, an event tag, or unclear?

    Duplicate detection needs the same judgement the prerequisite check makes,
    and having two implementations of "is this a base tag" is how they drift
    apart.
    """
    platform_key = platform_by_type.get(tag.get("type", ""))
    if not platform_key:
        return "unclear"
    flat = parameters_to_dict(tag.get("parameter"))
    text = " ".join(scalar_values(flat)).lower()
    platform = MEDIA_PLATFORMS[platform_key]
    base_marker = init_signal(platform_key, text)
    event_marker = event_signal(platform_key, text)
    return _classify_media_role(
        platform,
        flat,
        (tag.get("name") or "").lower(),
        base_marker,
        event_marker,
        template_hints.get(tag.get("type", "")),
    )


_ACCOUNT_SHAPE = re.compile(r"^(?:\d{4,20}|[A-Za-z0-9_-]{8,64})$")


def _looks_like_an_account(value: Any) -> bool:
    """Loose enough for any vendor, strict enough to skip `true` and `_gcl`."""
    return bool(_ACCOUNT_SHAPE.match(str(value).strip()))


def _detect_media_platforms(
    tags: list[dict[str, Any]], templates: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Find which third-party media platforms are present, and how.

    Community templates are opaque, so this weighs several signals:

    * STRONG -- the tag's type maps to an installed gallery template for this
      platform, or its Custom HTML contains the vendor's own snippet.
    * WEAK   -- a platform-specific parameter name, or the tag name.

    A tag is attributed to a platform only with one strong signal or two weak
    ones. Generic parameter names (`tagId`, `pixelId`, `advertiserId`, shared
    between platforms or with native Google tags) count for nothing on their
    own: they are the reason a Google Tag once registered as a Pinterest and a
    Microsoft base pixel simultaneously.
    """
    ambiguous = ambiguous_id_parameters()

    # Which vendor each installed template implements, and what contract it
    # declares. Each template states its own; read it rather than guessing.
    type_to_platform, hints_by_type = index_templates(templates)

    findings: dict[str, dict[str, Any]] = {
        key: {"setup_tags": [], "event_tags": [], "unclassified": []}
        for key in MEDIA_PLATFORMS
    }

    for tag in tags:
        tag_type = tag.get("type", "")
        if tag_type in _NATIVE_TAG_TYPES:
            continue

        name = (tag.get("name") or "").lower()
        flat = parameters_to_dict(tag.get("parameter"))
        # Settings rows are parameters too: a template that keeps its pixel id
        # in a table is invisible to a scan of the top level alone.
        param_keys = set(flat) | set(setting_values(flat))
        text_blob = " ".join(scalar_values(flat)).lower()

        # A tag whose type maps to a known template belongs to that platform
        # and to no other, however its parameters happen to be named. GTM's own
        # built-in vendor types (LinkedIn's `bzi`) say the same thing outright,
        # and were previously invisible here: a container's two native LinkedIn
        # tags went unreported while its two hand-written ones were found.
        mapped_platform = type_to_platform.get(tag_type) or NATIVE_MEDIA_TYPES.get(
            tag_type
        )

        for key, platform in MEDIA_PLATFORMS.items():
            if mapped_platform and mapped_platform != key:
                continue

            strong: list[str] = []
            weak: list[str] = []

            if mapped_platform == key:
                strong.append(
                    f"built-in {tag_type} tag type"
                    if tag_type in NATIVE_MEDIA_TYPES
                    else f"gallery template ({tag_type})"
                )

            base_marker = init_signal(key, text_blob)
            if base_marker:
                strong.append(base_marker)

            event_marker = event_signal(key, text_blob)
            if event_marker:
                strong.append(event_marker)

            specific_param = next(
                (p for p in platform.id_parameters if p in param_keys and p not in ambiguous),
                None,
            )
            if specific_param:
                weak.append(f"parameter '{specific_param}'")

            if any(keyword in name for keyword in platform.name_keywords):
                weak.append("tag name")

            # One strong signal, or two independent weak ones. Anything less is
            # a coincidence, not a detection.
            if not strong and len(weak) < 2:
                continue

            # The account id may still live in an ambiguous parameter; read it
            # only once the tag is attributed to this platform on other grounds.
            # The template's own id parameters come first: `partnerId` for
            # Criteo and `accountId` for Snapchat are not in any registry.
            hints = hints_by_type.get(tag_type) if mapped_platform == key else None
            preferred = list(hints["id_parameters"]) if hints else []
            id_param = next(
                (p for p in preferred + list(platform.id_parameters) if p in param_keys),
                specific_param,
            )
            if id_param is None and tag_type in NATIVE_MEDIA_TYPES:
                # A built-in type names its own parameter -- LinkedIn's `bzi`
                # calls the partner id simply `id`. Read whichever value is
                # shaped like an account rather than hardcoding one name per
                # type, which has been wrong every time it was guessed.
                id_param = next(
                    (k for k, v in flat.items() if _looks_like_an_account(v)), None
                )

            entry = {
                "tagId": tag.get("tagId"),
                "name": tag.get("name"),
                "type": tag_type,
                "signals": strong + weak,
                "confidence": "high" if strong else "medium",
                "account_id_value": flat.get(id_param) if id_param else None,
                "paused": tag.get("paused", False),
                "firingTriggerId": tag.get("firingTriggerId", []),
            }

            # A built-in vendor type IS the base tag; there is no event
            # variant of it to confuse it with.
            role = (
                "setup"
                if tag_type in NATIVE_MEDIA_TYPES
                else _classify_media_role(
                    platform, flat, name, base_marker, event_marker, hints
                )
            )
            bucket = {"setup": "setup_tags", "event": "event_tags"}.get(
                role, "unclassified"
            )
            findings[key][bucket].append(entry)

    return {k: v for k, v in findings.items() if any(v.values())}


@tool_errors
def check_tagging_prerequisites(
    product: str = "ga4",
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Check whether the container has the setup tags a product needs.

    ALWAYS call this before creating ANY event or conversion tag, for Google
    products and for third-party media alike. An event tag on a missing setup
    tag is the single most common silent failure in Tag Manager: the tag
    exists, the workspace looks fine, and no data is collected.

    Covers Google (`ga4`, `google_ads`, `floodlight`) and 35 third-party
    platforms. Pass `all` unless you know exactly which platform you mean --
    other users' containers carry vendors this one does not, and `all` reports
    only the platforms that leave a trace.

    Not every platform has a base tag to miss, and the check says which:

    * most are `library` -- Meta, TikTok, Pinterest, LinkedIn, Snapchat,
      Microsoft UET, X, Reddit, Criteo, Taboola, Outbrain, AdRoll, Quora,
      Amazon, Adform, RTB House, Teads, Yandex, LINE, Kakao, Naver, VK,
      HubSpot, Klaviyo, Segment, Mixpanel, Amplitude. Their event tags call a
      library the base tag loaded, so a missing base tag is **blocking**.
    * `standalone` -- Awin, Rakuten, Impact. Each tag carries its own account
      id, so there is nothing to be missing. Never report one as a fault.
    * `single` -- Hotjar, Clarity, Crazy Egg, Lucky Orange, Intercom. One
      install tag, no event tags. What matters is that it fires everywhere,
      once.

    Third-party pixels arrive as community templates whose API type is opaque
    (`cvt_<galleryTemplateId>`), so detection combines the gallery
    template owner, the tag's parameter keys, markers inside Custom HTML and
    the tag name. Each finding reports which signals matched and a confidence
    level -- treat `low` as "ask the user to confirm", not as absence.

    Args:
        product: "ga4", "google_ads", "floodlight", "all", or any platform
            key: "meta", "tiktok", "pinterest", "linkedin", "snapchat",
            "microsoft_ads", "x_twitter", "reddit", "criteo", "taboola",
            "outbrain", "adroll", "quora", "amazon_ads", "adform",
            "rtb_house", "teads", "awin", "rakuten", "impact",
            "yandex_metrica", "line", "kakao", "naver", "vk", "hubspot",
            "klaviyo", "segment", "mixpanel", "amplitude", "hotjar",
            "clarity", "crazy_egg", "lucky_orange", "intercom".
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        A dict with `ready` (bool), `checks` (one entry per requirement, with
        status, severity, why it matters and the remedy), `base_tags`,
        `media_platforms` and `blocking_issues`.
    """
    product = (product or "ga4").strip().lower()
    google_products: list[str] = []
    media_products: list[str] = []

    if product == "all":
        google_products = list(_PRODUCT_REQUIREMENTS)
        media_products = list(MEDIA_PLATFORMS)
    elif product in _PRODUCT_REQUIREMENTS:
        google_products = [product]
    elif product in MEDIA_PLATFORMS:
        media_products = [product]
    else:
        raise ValueError(
            f"Unknown product {product!r}. Use one of: "
            + ", ".join([*_PRODUCT_REQUIREMENTS, *MEDIA_PLATFORMS, "all"])
        )

    parent = settings.workspace_path(account_id, container_id, workspace_id)
    tags = paginate(workspaces().tags(), "list", "tag", parent=parent)
    triggers = paginate(workspaces().triggers(), "list", "trigger", parent=parent)
    templates = paginate(
        workspaces().templates(), "list", "template", parent=parent
    )

    by_type: dict[str, list[dict[str, Any]]] = {}
    for tag in tags:
        by_type.setdefault(tag.get("type", ""), []).append(tag)

    base_tags = [
        {
            "tagId": tag.get("tagId"),
            "name": tag.get("name"),
            "type": tag.get("type"),
            "label": BASE_TAG_TYPES[tag.get("type", "")],
            "destination_id": _base_tag_identifier(tag),
            "firingTriggerId": tag.get("firingTriggerId", []),
            "paused": tag.get("paused", False),
        }
        for tag_type in BASE_TAG_TYPES
        for tag in by_type.get(tag_type, [])
    ]

    checks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in google_products:
        for requirement in _PRODUCT_REQUIREMENTS[item]:
            key = (item, requirement["requirement"])
            if key in seen:
                continue
            seen.add(key)

            candidates = [
                t for tt in requirement["tag_types"] for t in by_type.get(tt, [])
            ]
            evaluation = evaluate_requirement(requirement, candidates)
            status = evaluation["status"]
            matches = evaluation["matches"]
            active_opaque = evaluation["opaque"]
            wrong_destination = evaluation["wrong_destination"]
            destination_note = evaluation["destination_note"]

            checks.append(
                {
                    "product": item,
                    "requirement": requirement["requirement"],
                    "label": requirement["label"],
                    "status": status,
                    "severity": requirement["severity"],
                    "why_it_matters": requirement["why"],
                    "found": [
                        {
                            "tagId": t.get("tagId"),
                            "name": t.get("name"),
                            "type": t.get("type"),
                            "destination_id": google_tag_destination(t),
                        }
                        for t in matches + active_opaque
                    ],
                    "wrong_destination": [
                        {
                            "tagId": t.get("tagId"),
                            "name": t.get("name"),
                            "destination_id": google_tag_destination(t),
                        }
                        for t in wrong_destination
                    ],
                    "destination_note": destination_note,
                    "remedy": requirement["remedy"] if status != "present" else None,
                }
            )

    # --- Third-party media setup tags -------------------------------------
    detected = _detect_media_platforms(tags, templates)
    template_by_type = {resolve_tag_type(t): t for t in templates}

    for item in media_products:
        platform = MEDIA_PLATFORMS[item]
        found = detected.get(item, {})
        setup_tags = found.get("setup_tags", [])
        event_tags = found.get("event_tags", [])
        unclassified = found.get("unclassified", [])

        active_setup = [t for t in setup_tags if not t["paused"]]
        if active_setup:
            status = "present" if any(t["firingTriggerId"] for t in active_setup) else "present_but_never_fires"
        elif setup_tags:
            status = "present_but_paused"
        elif unclassified:
            status = "uncertain"
        else:
            status = "missing"

        # Only report a platform the user asked about, or one with any trace.
        if status == "missing" and product == "all" and not (event_tags or unclassified):
            continue

        # Some vendor templates inject the pixel library themselves, so their
        # event tags still send data with no base tag -- Meta and Pinterest do,
        # TikTok does not. Calling both cases "blocking" would be wrong in one
        # direction and alarmist in the other, so read it from the template.
        bootstrapping = None
        for event_tag in event_tags:
            template = template_by_type.get(event_tag["type"])
            if template is not None:
                bootstrapping = template_bootstraps_library(template)
                break

        # Not every platform has a base tag to miss. An Awin sale tag carries
        # its own advertiser id, and Hotjar has no event tags at all. Reporting
        # "missing base tag" for those would be a limitation the agent invented.
        if platform.event_model == "standalone":
            severity = "informational"
            why = (
                f"{platform.label} tags are self-contained: each carries the "
                "account id and the conversion details, so no base tag has to "
                "run before them. Nothing is missing here."
            )
        elif platform.event_model == "single":
            severity = "recommended"
            why = (
                f"{platform.label} installs as a single tag with no event tags "
                "depending on it. What matters is that it fires on every page: "
                "a gap in coverage loses sessions silently, and a second copy "
                "records everything twice."
            )
        elif status == "present":
            severity = "blocking"
            why = (
                f"{platform.label} event tags depend on the base tag having "
                "loaded the pixel library and registered the account id."
            )
        elif bootstrapping:
            severity = "high"
            why = (
                f"The installed {platform.label} template loads the pixel "
                "library itself, so these event tags do send data. What is "
                "missing is a base tag on Initialization - All Pages: without "
                "it the pixel only initializes on pages where an event fires, "
                "so page views, audience building and view-through attribution "
                "are all incomplete."
            )
        else:
            severity = "blocking"
            why = (
                f"{platform.label} event tags call a JavaScript library that "
                "only exists once the base tag has loaded it and registered "
                "the account id. Without it the event tag runs, fails "
                "silently, and sends nothing."
                + (
                    " Confirmed for this container: the installed template has "
                    "no script-injection permission, so it cannot load the "
                    "library on its own."
                    if bootstrapping is False
                    else ""
                )
            )

        checks.append(
            {
                "product": item,
                "requirement": "setup_tag",
                "label": f"{platform.label} setup (base) tag",
                "status": status,
                "severity": severity,
                "template_self_bootstraps": bootstrapping,
                "why_it_matters": why,
                "found": setup_tags,
                "event_tags_already_present": event_tags,
                "possibly_related_unclassified": unclassified,
                "expected_id_format": platform.id_format,
                "event_model": platform.event_model,
                "remedy": (
                    None
                    if status == "present" or platform.event_model == "standalone"
                    else platform.setup_guidance
                ),
                "detection_note": (
                    "Third-party pixels are community templates with opaque API "
                    "types, so this is heuristic. A `low` confidence finding or "
                    "an `uncertain` status means: ask the user to confirm before "
                    "creating a second base tag."
                ),
            }
        )

    consent = evaluate_consent_initialization(tags, triggers)
    checks.append(
        {
            "product": "consent",
            "requirement": "consent_initialization",
            "label": "A tag firing on Consent Initialization",
            "status": consent["status"],
            "severity": "recommended",
            "why_it_matters": (
                "Consent Mode must be initialized before any measurement tag "
                "fires. Without it, tags may run before the user's choice is "
                "known. Note this checks for a TAG on the reserved Consent "
                "Initialization trigger: that trigger is built in and never "
                "appears in `list_triggers`."
            ),
            "found": [
                {"tagId": t.get("tagId"), "name": t.get("name"), "type": t.get("type")}
                for t in consent["tags"]
            ],
            "remedy": consent["remedy"],
        }
    )

    blocking = [
        c
        for c in checks
        if c["severity"] == "blocking" and c["status"] not in ("present", "uncertain")
    ]

    dependent_counts = {
        tag_type: len(by_type.get(tag_type, [])) for tag_type in DEPENDENT_TAG_TYPES
    }

    # Only a second base tag for the SAME destination double-counts. One
    # Google Tag for G-XXXX and another for AW-XXXX is a normal setup, and
    # reporting it as a duplicate trains the user to ignore these warnings.
    warnings: list[str] = []
    google_tags = [
        b for b in base_tags if b["type"] in ("googtag", "gaawc") and not b["paused"]
    ]
    by_destination: dict[str, list[str]] = {}
    for base in google_tags:
        by_destination.setdefault(base["destination_id"] or "(no id)", []).append(
            f"{base['name']} (id {base['tagId']})"
        )
    for destination, names in by_destination.items():
        if len(names) > 1:
            warnings.append(
                f"{len(names)} base Google Tags point at {destination}: "
                + ", ".join(names)
                + ". Duplicate base tags on one destination double-count every "
                "page view. Confirm which to keep before adding event tags."
            )
    if len(by_destination) > 1:
        warnings.append(
            "Multiple Google Tag destinations configured ("
            + ", ".join(by_destination)
            + "). This is normal when one container feeds GA4 and Google Ads; "
            "confirm each destination is intended."
        )
    linkers = [b for b in base_tags if b["type"] == "gclidw" and not b["paused"]]
    if len(linkers) > 1:
        warnings.append(
            f"{len(linkers)} Conversion Linkers found. Keep exactly one."
        )

    for key, found in detected.items():
        active_setup = [t for t in found.get("setup_tags", []) if not t["paused"]]
        if len(active_setup) < 2:
            continue

        label = MEDIA_PLATFORMS[key].label
        names = [f"{t['name']} (id {t['tagId']})" for t in active_setup]
        account_ids = [t.get("account_id_value") for t in active_setup]
        known_ids = [i for i in account_ids if i]

        if len(known_ids) == len(active_setup) and len(set(known_ids)) == 1:
            warnings.append(
                f"{label}: {len(active_setup)} setup tags share account id "
                f"{known_ids[0]} -- " + ", ".join(names) + ". This duplicates "
                "every hit for that pixel."
            )
        elif len(set(known_ids)) == len(known_ids) and len(known_ids) == len(active_setup):
            warnings.append(
                f"{label}: {len(active_setup)} setup tags with different account "
                "ids (" + ", ".join(known_ids) + "). Legitimate when the site "
                "reports to several ad accounts -- confirm with the user rather "
                "than removing one."
            )
        else:
            warnings.append(
                f"{label}: {len(active_setup)} possible setup tags -- "
                + ", ".join(names)
                + ". The account id could not be read from all of them, so this "
                "may not be a duplicate. Verify before changing anything."
            )

    return {
        "parent": parent,
        "products_checked": google_products + media_products,
        "ready": not blocking,
        "blocking_issues": [
            f"{c['product']}: {c['label']} is {c['status']}" for c in blocking
        ],
        "warnings": warnings,
        "checks": checks,
        "base_tags": base_tags,
        "media_platforms_detected": {
            key: {
                "label": MEDIA_PLATFORMS[key].label,
                "setup_tags": len(found.get("setup_tags", [])),
                "event_tags": len(found.get("event_tags", [])),
                "unclassified": len(found.get("unclassified", [])),
            }
            for key, found in detected.items()
        },
        "installed_templates": [
            {
                "name": t.get("name"),
                "tag_type": resolve_tag_type(t),
                "gallery_owner": (t.get("galleryReference") or {}).get("owner"),
            }
            for t in templates
        ],
        "dependent_tag_counts": {k: v for k, v in dependent_counts.items() if v},
        "note": (
            "`ready: false` means you must create the missing setup tag FIRST, "
            "in the same plan, before the tag the user asked for. For "
            "third-party pixels the setup tag usually requires installing a "
            "community template, which this agent cannot do -- tell the user "
            "what to install and ask for the account id."
        ),
    }
