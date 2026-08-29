"""Which tags initialise a pixel, and which ones duplicate each other.

Duplication is a question about **base tags**. Most platforms carry the account
id only in the initialisation call, and their event tags use whichever library
that call loaded:

    fbq('init', '123')            <- the account lives here
    fbq('track', 'AddToCart')     <- no account; uses the pixel above

Comparing every tag by `(account, event)` therefore reports noise. Twenty GA4
tags firing `click` on twenty pages are twenty legitimate tags. The question
that matters is narrower: **is this account initialised more than once?** Two
initialisations double every hit on the site.

Three kinds of finding come out of this file:

1. `base` -- the same account initialised twice, whether by native Google tag,
   community template, hand-written script or image pixel.
2. `conversion` -- two conversion tags with an identical configuration. Unlike
   a GA4 event, a Google Ads conversion carries its own id and label, so a
   second one on the same trigger is a double-counted conversion.
3. `script` -- two Custom HTML tags whose scripts are identical modulo
   whitespace and `{{Variable}}` references. This is what catches a vendor no
   registry has heard of.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from typing import Optional

from .gtm_client import parameters_to_dict
from .gtm_client import scalar_values
from .gtm_client import setting_values
from .vendor_snippets import find_event_only_platforms
from .vendor_snippets import find_initialisations
from .vendor_snippets import platform_label
from .vendor_snippets import script_fingerprint

#: Native Google tag types that CONFIGURE a destination. These are base tags.
_NATIVE_BASE = {
    "googtag": ("google_tag", "tagId"),
    "gaawc": ("ga4_config", "measurementId"),
}

#: Conversion tags. They carry their own account and label, so an identical
#: pair is a double-counted conversion rather than a legitimate repeat. GA4
#: events are deliberately absent: repeating one event name across pages is
#: normal and reporting it is noise.
_CONVERSION_CONFIG = {
    "awct": ("google_ads_conversion", ("conversionId", "conversionLabel")),
    "sp": ("google_ads_remarketing", ("conversionId",)),
    "flc": ("floodlight_counter", ("advertiserId", "groupTag", "activityTag")),
    "fls": ("floodlight_sales", ("advertiserId", "groupTag", "activityTag")),
}

#: Shared with duplicate detection, which labels the same products. Two
#: copies of this table meant one of them was always a little out of date.
PRODUCT_LABELS = {
    "google_tag": "Google Tag",
    "ga4_config": "GA4 Configuration",
    "google_ads_conversion": "Google Ads Conversion",
    "google_ads_remarketing": "Google Ads Remarketing",
    "floodlight_counter": "Floodlight Counter",
    "floodlight_sales": "Floodlight Sales",
}

_REFERENCE = re.compile(r"^\{\{([^{}]+)\}\}$")

#: A Google destination configured by hand instead of by a Google Tag. This is
#: how gtag.js is installed outside Tag Manager, and containers migrating INTO
#: GTM carry it as Custom HTML for months. Without these patterns a hand-written
#: GA4 install and a Google Tag for the same property look unrelated, which is
#: precisely the "manual vs automatic" comparison that has to work.
_GTAG_CONFIG = (
    re.compile(
        r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]"
        r"((?:G|AW|DC|GT|UA)-[A-Z0-9-]+|\{\{[^{}]+\}\})['\"]",
        re.IGNORECASE,
    ),
    re.compile(
        r"googletagmanager\.com/gtag/js\?id="
        r"((?:G|AW|DC|GT|UA)-[A-Z0-9-]+|\{\{[^{}]+\}\})",
        re.IGNORECASE,
    ),
)

#: A Google Ads conversion written by hand: `send_to: 'AW-123/AbCdEf'`.
_GTAG_CONVERSION = re.compile(
    r"['\"]?send_to['\"]?\s*:\s*['\"](AW-\d+)/([A-Za-z0-9_-]+)['\"]",
    re.IGNORECASE,
)

#: A Floodlight activity written by hand, as an iframe/image counter.
#: `.../activityi;src=13520834;type=sale;cat=purch0;...`
_FLOODLIGHT_TAG = re.compile(
    r"src=(\d{4,12})[;&]\s*type=([A-Za-z0-9_-]+)[;&]\s*cat=([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


#: The parameters that make a tag what it is, per type. Comparing these is what
#: replaced a heuristic that only looked at values SHAPED like an id -- which
#: silently ignored Floodlight's `groupTag` and `activityTag` (short words, no
#: digits) and so declared every new activity on an advertiser a duplicate of
#: every other one.
IDENTITY_KEYS: dict[str, tuple[str, ...]] = {
    "googtag": ("tagId",),
    "gaawc": ("measurementId",),
    "gaawe": ("measurementId", "eventName"),
    "awct": ("conversionId", "conversionLabel"),
    "sp": ("conversionId",),
    "flc": ("advertiserId", "groupTag", "activityTag"),
    "fls": ("advertiserId", "groupTag", "activityTag"),
    #: Exactly one Conversion Linker belongs in a container, so its identity is
    #: the empty tuple: any second one is the same tag.
    "gclidw": (),
}


def google_destinations_in(text: str) -> list[str]:
    """Destination ids configured by a hand-written gtag snippet."""
    found: list[str] = []
    for pattern in _GTAG_CONFIG:
        for match in pattern.finditer(text):
            value = match.group(1)
            if value not in found:
                found.append(value)
    return found


def google_conversions_in(text: str) -> list[tuple[str, tuple[str, ...]]]:
    """Google Ads conversions and Floodlight activities written by hand.

    A Floodlight activity is very often an image or iframe counter pasted into
    Custom HTML rather than an `flc` tag, and a Google Ads conversion is often
    a `gtag('event', 'conversion', {send_to: ...})`. Comparing only the native
    tag types would miss half the conversions in an inherited container.
    """
    found: list[tuple[str, tuple[str, ...]]] = []
    for match in _GTAG_CONVERSION.finditer(text):
        found.append(
            ("google_ads_conversion", (match.group(1).replace("AW-", ""), match.group(2)))
        )
    for match in _FLOODLIGHT_TAG.finditer(text):
        found.append(
            ("floodlight_counter", (match.group(1), match.group(2), match.group(3)))
        )
    return found


@dataclass(frozen=True)
class Initialisation:
    """One place where an account is configured."""

    product: str
    account: str
    #: "native", "template", "html" -- the same account reached three ways.
    implementation: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.product, self.account.upper())

    @property
    def label(self) -> str:
        return f"{PRODUCT_LABELS.get(self.product, platform_label(self.product))} / {self.account}"


def _literal(value: Any, constants: dict[str, str]) -> Optional[str]:
    """Resolve a constant reference so a variable compares with a literal."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    reference = _REFERENCE.match(text)
    if reference:
        return constants.get(reference.group(1).strip()) or text
    return text


def _script_body(flat: dict[str, Any]) -> str:
    """Raw parameter values, never a JSON dump.

    `json.dumps` escapes `"` as `\\"`, which stops every double-quoted snippet
    from matching. That silently hid all the LinkedIn tags in one container
    while Meta kept working, purely because Meta's snippet uses single quotes.

    `scalar_values` reaches into nested tables as well: configuration is not
    only top-level parameters, and a search that reads one level finds one
    level.
    """
    return "\n".join(scalar_values(flat))


def initialisations_of(
    tag: dict[str, Any],
    *,
    platform_by_type: Optional[dict[str, str]] = None,
    template_hints: Optional[dict[str, dict[str, Any]]] = None,
    constants: Optional[dict[str, str]] = None,
    template_roles: Optional[dict[str, str]] = None,
    **_unused: Any,
) -> list[Initialisation]:
    """Every account this tag initialises. Empty for an event-only tag.

    Args:
        tag: the tag resource from the API.
        platform_by_type: `cvt_` tag type -> media platform key.
        template_hints: `cvt_` tag type -> `template_role_hints` output.
        constants: constant-variable name -> value.
        template_roles: tag id -> "setup" / "event" / "unclear", from the media
            role classifier. Only a setup-role template tag initialises.
        _unused: callers splat the whole shared container context in. Ignoring
            the keys this function does not read means a new one -- the
            variable-candidate map, say -- cannot break it from a distance.
    """
    platform_by_type = platform_by_type or {}
    template_hints = template_hints or {}
    constants = constants or {}
    template_roles = template_roles or {}

    tag_type = tag.get("type", "")
    flat = parameters_to_dict(tag.get("parameter"))

    if tag_type in _NATIVE_BASE:
        product, key = _NATIVE_BASE[tag_type]
        account = _literal(flat.get(key), constants)
        return [Initialisation(product, account, "native")] if account else []

    platform = platform_by_type.get(tag_type)
    if platform:
        if template_roles.get(str(tag.get("tagId"))) != "setup":
            return []  # an event tag on a template configures no account
        hints = template_hints.get(tag_type, {})
        # A template may declare its id as a top-level field or as a row in a
        # settings table; the top level wins where both exist.
        readable = {**setting_values(flat), **flat}
        account_key = next(
            (p for p in hints.get("id_parameters", []) if readable.get(p)), None
        )
        account = (
            _literal(readable.get(account_key), constants) if account_key else None
        )
        return [Initialisation(platform, account, "template")] if account else []

    if tag_type in ("html", "img"):
        body = _script_body(flat)
        # A hand-written pixel usually parameterises its id. Resolving the
        # constant here is what makes `fbq('init', '{{CONST - Pixel ID}}')` and
        # a template tag holding 156914648903155 read as the same account --
        # without it, a migration from Custom HTML to a template looks like two
        # unrelated pixels instead of one duplicated one.
        initialisations = [
            Initialisation(key, _literal(account, constants) or account, "html")
            for key, account in find_initialisations(body)
        ]
        # A hand-written `gtag('config', 'G-...')` configures the destination
        # exactly as a Google Tag does. Reported under the same product so the
        # two compare with each other.
        initialisations += [
            Initialisation("google_tag", _literal(destination, constants) or destination, "html")
            for destination in google_destinations_in(body)
        ]
        return initialisations

    return []


def conversion_config_of(
    tag: dict[str, Any], constants: Optional[dict[str, str]] = None
) -> Optional[tuple[str, tuple[str, ...]]]:
    """The full configuration of a conversion tag, or None if it is not one."""
    entry = _CONVERSION_CONFIG.get(tag.get("type", ""))
    if not entry:
        return None
    product, keys = entry
    flat = parameters_to_dict(tag.get("parameter"))
    values = tuple((_literal(flat.get(k), constants or {}) or "") for k in keys)
    if not any(values):
        return None
    return product, values


def event_only_platforms(tag: dict[str, Any]) -> list[str]:
    """Vendors this tag calls without initialising -- it depends on a base tag."""
    if tag.get("type") not in ("html", "img"):
        return []
    return find_event_only_platforms(_script_body(parameters_to_dict(tag.get("parameter"))))


def html_fingerprint(tag: dict[str, Any]) -> Optional[str]:
    """Structural hash of a Custom HTML body, for vendors no registry names."""
    if tag.get("type") not in ("html", "img"):
        return None
    return script_fingerprint(_script_body(parameters_to_dict(tag.get("parameter"))))


def describe_base_overlap(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Judge several initialisations of one account.

    Any second initialisation is a real problem -- the library loads twice and
    every automatic hit is sent twice. Severity distinguishes how certain that
    is, not whether it matters.
    """
    active = [e for e in entries if not e["paused"]]
    if len(active) < 2:
        return {"severity": None, "reason": None}

    implementations = {e["implementation"] for e in active}
    trigger_sets = [frozenset(e["firingTriggerId"]) for e in active]
    shared = any(a & b for i, a in enumerate(trigger_sets) for b in trigger_sets[i + 1 :])

    if shared:
        return {
            "severity": "critical",
            "reason": (
                "The same account is initialised more than once on the same "
                "trigger. The library loads twice and every hit is duplicated."
            ),
        }
    if len(implementations) > 1:
        return {
            "severity": "critical",
            "reason": (
                "The same account is initialised in more than one way ("
                + ", ".join(sorted(implementations))
                + "). One is a leftover from a migration; both still run."
            ),
        }
    return {
        "severity": "high",
        "reason": (
            "The same account is initialised by more than one tag. Unless the "
            "triggers are mutually exclusive -- different domains or "
            "environments -- this loads the pixel twice."
        ),
    }
