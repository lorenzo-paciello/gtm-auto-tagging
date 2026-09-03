"""Would writing this tag duplicate something already in the workspace?

This runs BEFORE `create_tag` and `update_tag` write anything, and they refuse
until the user has seen the answer. Reporting a duplicate afterwards leaves the
workspace dirty and puts the cleanup on the user.

It is a different question from the audit in `gtm_duplicates`. The audit
compares base tags only, because twenty GA4 event tags firing `click` on twenty
pages are twenty legitimate tags and grouping them is noise. Here the user is
proposing one specific tag, so more comparisons are worth making -- but every
one of them still has to be *right*, because a false block is worse than a
missed warning: it teaches the user to pass `confirm_duplicate` without reading.

## The comparisons, and why each exists

| Kind | Blocks | What it catches |
| --- | --- | --- |
| `initialisation` | yes | the account is already configured -- native tag, template, Custom HTML or hand-written `gtag('config', ...)` |
| `already_sent_by_a_base_tag` | yes | the event is already automatic: a Google Tag sends `page_view` itself unless `send_page_view` is false; a base pixel fires its own PageView |
| `identical_configuration` | yes | a tag of this type already has the same identity |
| `duplicate_conversion` | yes | the same Google Ads conversion or Floodlight activity, native or hand-written |
| `possible_duplicate_via_variable` | yes | an existing tag's id is a lookup table that can produce this id |
| `identical_script` | yes | the same hand-written script, for any vendor |
| `duplicate_event_for_account` | if triggers overlap | this platform already sends this event for this account |
| `same_identifier` | no | the id appears elsewhere -- context, not a fault |
| `missing_prerequisite` | no | the foundation this tag needs is absent |
| `prefer_template` | no | a template for this platform is installed; Custom HTML is the fallback |

## Two rules the identity comparison had to learn the hard way

**Compare the parameters that define the tag, not the ones that look like ids.**
The first version compared values *shaped* like an identifier. Floodlight's
`groupTag` (`sale`) and `activityTag` (`purch0`) are short words, so they were
ignored, and every new activity on an advertiser compared identical to every
other one -- the check would have blocked every Floodlight tag a user ever
created. `IDENTITY_KEYS` states what actually identifies each type; anything
not listed falls back to full parameter equality, which cannot over-match.

**A variable is not always one value.** One real container routes GA4 by a
RegEx table mapping 27 URL patterns to 27 measurement ids, behind a single
Google Tag. Resolving only Constants sees `{{[ED]ID-Metrica-Estados}}`,
resolves nothing, and calls a new Google Tag for one of those 27 properties
clean.
"""

from __future__ import annotations

import json
import re
from typing import Any
from typing import Optional

from .gtm_client import parameters_to_dict
from .gtm_client import scalar_values
from .gtm_client import setting_values
from .gtm_client import tool_errors
from .gtm_duplicates import _entry
from .gtm_duplicates import _fetch
from .media_platforms import MEDIA_PLATFORMS
from .tag_identity import IDENTITY_KEYS
from .tag_identity import PRODUCT_LABELS
from .tag_identity import google_conversions_in
from .tag_identity import initialisations_of
from .vendor_snippets import find_event_only_platforms
from .vendor_snippets import find_initialisations
from .vendor_snippets import platform_label

# ---------------------------------------------------------------------------
# Reading a payload
# ---------------------------------------------------------------------------

#: Shapes an account identifier takes. Deliberately vendor-agnostic: the point
#: is to recognise an identifier in a container carrying tools no registry
#: names, so the agent can still ask "does this id already exist here?"
_IDENTIFIER_SHAPES = (
    re.compile(r"^(?:G|AW|DC|GT|UA)-[A-Z0-9-]{4,}$", re.IGNORECASE),
    re.compile(r"^\d{5,20}$"),
    re.compile(r"^t2_[A-Za-z0-9]+$"),
    re.compile(r"^VK-RTRG-[A-Za-z0-9-]+$", re.IGNORECASE),
    re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    ),
)

_REFERENCE_ONLY = re.compile(r"^\{\{[^{}]+\}\}$")

#: An event a base tag already sends by itself.
_PAGE_VIEW_EVENTS = {
    "page_view",
    "pageview",
    "page view",
    "pagevisit",
    "page_visit",
    "pv",
}

#: A hand-written tag states its event inside the script, not in a parameter,
#: so the page view has to be read out of the body: fbq('track','PageView'),
#: ttq.page(), pintrk('page'), rdt('track','PageVisit').
_HTML_PAGE_VIEW = re.compile(
    r"""['"](?:page[_ ]?view|pagevisit|page[_ ]?visit|pv)['"]|\.page\(|\(\s*['"]page['"]\s*\)""",
    re.IGNORECASE,
)

#: Names for the same switch. GTM's own tags use the snake_case gtag field;
#: templates and the legacy GA4 Configuration use variations.
_PAGE_VIEW_SWITCHES = (
    "send_page_view",
    "sendPageView",
    "sendPageViewEvent",
    "send_page_view_event",
)

#: Types whose identity is a duplicate wherever it fires. A second GA4
#: `select_item` on a different list is ordinary work; a second Google Ads
#: conversion with the same id and label is the same conversion action counted
#: twice, and Google Ads cannot tell the two tags apart. Reported live: a
#: duplicate conversion passed the gate because its trigger differed.
_IDENTITY_ALWAYS_BLOCKS = {
    "awct",
    "sp",
    "flc",
    "fls",
    "googtag",
    "gaawc",
    "gclidw",
}

#: What each product needs underneath it. The prerequisite check is the
#: authority; this is the reminder at the moment of writing, so a plan that
#: forgot it does not produce a tag that silently sends nothing.
_FOUNDATIONS: dict[str, tuple[str, ...]] = {
    "awct": ("conversion_linker", "google_ads_destination"),
    "sp": ("conversion_linker", "google_ads_destination"),
    "flc": ("conversion_linker",),
    "fls": ("conversion_linker",),
    "gaawe": ("ga4_destination",),
}


def looks_like_an_identifier(value: Any) -> bool:
    """Is this value an account identifier rather than a setting or a label?

    Registry-free on purpose. `find_initialisations` knows 35 vendors by their
    init call; this knows none, and recognises an id by its shape alone. That
    is what lets the agent cope with a container full of tools nobody
    anticipated: it can still answer "this number already appears in tag 327".
    """
    text = str(value).strip()
    if not text or len(text) > 128:
        return False
    if _REFERENCE_ONLY.match(text):
        return True  # `{{CONST - Pixel ID}}` names one specific thing
    if " " in text or "/" in text or "<" in text:
        return False
    if any(shape.match(text) for shape in _IDENTIFIER_SHAPES):
        return True
    # A bare token long enough not to be a word, mixing letters and digits:
    # pixel codes, write keys, conversion labels, advertiser hashes.
    if len(text) >= 8 and re.fullmatch(r"[A-Za-z0-9_-]+", text):
        return any(c.isdigit() for c in text) and any(c.isalpha() for c in text)
    return False


def _event_parameter_names() -> set[str]:
    """Parameter keys that carry an event name, gathered from the registry."""
    names = {"eventName", "event_name", "event", "eventType", "standardEventName"}
    for platform in MEDIA_PLATFORMS.values():
        names.update(platform.event_parameters)
    return {n.lower() for n in names}


def _resolve(value: Any, constants: dict[str, str], tags_by_name: dict[str, Any]) -> str:
    """Resolve a constant reference or a tagReference down to a literal."""
    if isinstance(value, dict):
        if value.get("__type__") == "tagReference":
            referenced = tags_by_name.get(str(value.get("value", "")).strip().lower())
            if referenced:
                flat = parameters_to_dict(referenced.get("parameter"))
                for key in ("tagId", "measurementId"):
                    if flat.get(key):
                        return str(flat[key]).strip()
            return str(value.get("value", "")).strip()
        return ""
    text = str(value).strip()
    if _REFERENCE_ONLY.match(text):
        return constants.get(text[2:-2].strip()) or text
    return text


def _possible_values(
    value: Any, constants: dict[str, str], candidates: dict[str, set[str]]
) -> set[str]:
    """Every literal a parameter could hold, following one level of lookup."""
    text = str(value).strip()
    if _REFERENCE_ONLY.match(text):
        name = text[2:-2].strip()
        if name in constants:
            return {constants[name]}
        return set(candidates.get(name, {text}))
    return {text} if text else set()


#: Parameters that point at a variable holding a block of settings.
_SETTINGS_REFERENCES = (
    "configSettingsVariable",
    "eventSettingsVariable",
    "userPropertiesVariable",
)


def _readable(
    flat: dict[str, Any], settings_variables: Optional[dict[str, dict[str, str]]] = None
) -> dict[str, Any]:
    """Everything the tag configures, wherever the value actually lives.

    Three levels, because GTM offers three and containers use all of them:

    1. top-level parameters
    2. rows of a nested settings table (`configSettingsTable`, `fieldsToSet`)
    3. rows of a **settings variable** the tag merely references

    Level 2 was missed once and told a user their page_view tag would
    double-count on a property where they had just turned `send_page_view`
    off. Level 3 is the same mistake one indirection further out, and it is
    common in governed containers: the settings live in one variable so that
    twenty tags share them.
    """
    from_variables: dict[str, Any] = {}
    for key in _SETTINGS_REFERENCES:
        reference = str(flat.get(key, "")).strip()
        if settings_variables and _REFERENCE_ONLY.match(reference):
            from_variables.update(
                settings_variables.get(reference[2:-2].strip(), {})
            )
    return {**from_variables, **setting_values(flat), **flat}


def _identity_of(
    tag_type: str,
    flat: dict[str, Any],
    constants: dict[str, str],
    tags_by_name: dict[str, Any],
) -> Optional[tuple[Any, ...]]:
    """What makes this tag this tag, or None when the type declares no identity.

    For a known type it is the declared `IDENTITY_KEYS`. For anything else --
    a community template, a Custom HTML tag, a type added to GTM tomorrow --
    it is the whole parameter set, which cannot over-match.
    """
    # A hand-written tag's identity is its script, normalised for whitespace
    # and variable references -- `identical_script` says so far more usefully
    # than raw parameter equality, which would also match on a stray space.
    if tag_type in ("html", "img"):
        return None

    readable = _readable(flat)
    keys = IDENTITY_KEYS.get(tag_type)
    if keys is not None:
        values = tuple(
            _resolve(readable.get(key, ""), constants, tags_by_name).lower()
            for key in keys
        )
        # `gclidw` declares no keys: exactly one Conversion Linker belongs in a
        # container, so any second one is the same tag.
        return values if (values and any(values)) or keys == () else None
    return tuple(
        sorted(
            (key, _resolve(value, constants, tags_by_name))
            for key, value in readable.items()
            if isinstance(value, (str, int, float, bool))
        )
    )


def _candidate_identity(
    config: dict[str, Any], constants: dict[str, str], tags_by_name: dict[str, Any]
) -> tuple[set[str], set[str]]:
    """The identifiers and event names this payload carries."""
    event_keys = _event_parameter_names()
    identifiers: set[str] = set()
    events: set[str] = set()

    pairs: list[tuple[str, Any]] = list(config.items())
    pairs += list(setting_values(config).items())

    for key, raw in pairs:
        value = _resolve(raw, constants, tags_by_name)
        if not value:
            continue
        # The parameter NAME decides. `eventName: "scroll_75"` is an event even
        # though it has the shape of an identifier; classifying it as one made
        # two unrelated scroll tags compare as identical.
        if key.lower() in event_keys:
            events.add(value.strip().lower())
        elif looks_like_an_identifier(value):
            identifiers.add(value)
    return identifiers, events


def _tag_text(tag: dict[str, Any], constants: dict[str, str]) -> str:
    """A tag's values as one blob, with constants expanded."""
    flat = parameters_to_dict(tag.get("parameter"))
    blob = "\n".join(scalar_values(flat))
    for name, value in constants.items():
        blob = blob.replace("{{" + name + "}}", str(value))
    return blob


def _mentions(value: str, text: str) -> bool:
    return (
        re.search(r"(?<![A-Za-z0-9_-])" + re.escape(value) + r"(?![A-Za-z0-9_-])", text)
        is not None
    )


def _body_of(config: dict[str, Any]) -> str:
    return "\n".join(scalar_values(config))


def _sends_its_own_page_view(
    tag: dict[str, Any],
    constants: dict[str, str],
    settings_variables: Optional[dict[str, dict[str, str]]] = None,
) -> bool:
    """A GA4 base tag sends `page_view` unless it was told not to.

    The switch is almost never a top-level parameter, so this reads the nested
    tables. An unresolvable value is treated as the default, which is on:
    guessing "off" would let a real duplicate through, and on is what GTM
    applies.
    """
    settings = _readable(parameters_to_dict(tag.get("parameter")), settings_variables)
    for key in _PAGE_VIEW_SWITCHES:
        if key not in settings:
            continue
        text = str(settings[key]).strip()
        if _REFERENCE_ONLY.match(text):
            text = constants.get(text[2:-2].strip(), text)
        if text.strip().lower() in ("false", "0", "no"):
            return False
    return True


def _conversions_of(
    tag: dict[str, Any], constants: dict[str, str], tags_by_name: dict[str, Any]
) -> list[tuple[str, tuple[str, ...]]]:
    """Google Ads conversions and Floodlight activities, however implemented.

    A native `awct` and a hand-written `gtag('event','conversion',{send_to:
    'AW-123/label'})` are the same conversion. So are an `flc` tag and the
    iframe counter someone pasted into Custom HTML. Comparing only the native
    types would miss half the conversions in an inherited container.
    """
    tag_type = tag.get("type", "")
    flat = parameters_to_dict(tag.get("parameter"))
    readable = _readable(flat)

    native = {
        "awct": ("google_ads_conversion", ("conversionId", "conversionLabel")),
        "sp": ("google_ads_remarketing", ("conversionId",)),
        "flc": ("floodlight_counter", ("advertiserId", "groupTag", "activityTag")),
        "fls": ("floodlight_counter", ("advertiserId", "groupTag", "activityTag")),
    }
    if tag_type in native:
        product, keys = native[tag_type]
        values = tuple(
            _resolve(readable.get(key, ""), constants, tags_by_name).lower()
            for key in keys
        )
        return [(product, values)] if any(values) else []

    if tag_type in ("html", "img"):
        return [
            (product, tuple(v.lower() for v in values))
            for product, values in google_conversions_in(_tag_text(tag, constants))
        ]
    return []


def _candidate_platform(
    tag_type: str, config: dict[str, Any], context: dict[str, Any]
) -> Optional[str]:
    """Which media platform this payload belongs to, template or hand-written."""
    platform = context.get("platform_by_type", {}).get(tag_type)
    if platform:
        return platform
    if tag_type in ("html", "img"):
        body = _body_of(config)
        initialised = find_initialisations(body)
        if initialised:
            return initialised[0][0]
        event_only = find_event_only_platforms(body)
        if event_only:
            return event_only[0]
    return None


def _initialisations_by_product(
    tags: list[dict[str, Any]], context: dict[str, Any]
) -> dict[str, list[tuple[dict[str, Any], Any]]]:
    grouped: dict[str, list[tuple[dict[str, Any], Any]]] = {}
    for tag in tags:
        for init in initialisations_of(tag, **context):
            grouped.setdefault(init.product, []).append((tag, init))
    return grouped


def _equivalents_in(
    tag_type: str,
    config: dict[str, Any],
    tags: list[dict[str, Any]],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Tags already initialising what this payload would initialise."""
    candidate = {
        "tagId": "__candidate__",
        "type": tag_type,
        "name": "__candidate__",
        "parameter": [
            {"key": k, "value": v if isinstance(v, str) else str(v)}
            for k, v in config.items()
        ],
    }
    candidate_context = dict(context)
    candidate_context["template_roles"] = {"__candidate__": "setup"}
    wanted = {init.key for init in initialisations_of(candidate, **candidate_context)}
    if not wanted:
        return []
    return [
        _entry(tag, implementation=init.implementation, identity=init.label)
        for tag in tags
        for init in initialisations_of(tag, **context)
        if init.key in wanted
    ]


def _shares_a_trigger(candidate_triggers: set[str], tag: dict[str, Any]) -> bool:
    existing = {str(t) for t in tag.get("firingTriggerId") or []}
    if not candidate_triggers or not existing:
        return True  # unknown overlap: assume the worst, ask the user
    return bool(candidate_triggers & existing)


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------


def collect_conflicts(
    tag_type: str,
    config: dict[str, Any],
    name: str,
    tags: list[dict[str, Any]],
    context: dict[str, Any],
    exclude_tag_id: Optional[str] = None,
    firing_trigger_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Every reason this payload might already exist. No API calls."""
    # An update compares the new configuration with every OTHER tag. Without
    # this, editing a tag would always conflict with itself.
    if exclude_tag_id is not None:
        tags = [t for t in tags if str(t.get("tagId")) != str(exclude_tag_id)]

    constants = context.get("constants", {})
    candidates = context.get("variable_candidates", {})
    settings_vars = context.get("settings_variables", {})
    tags_by_name = {str(t.get("name", "")).strip().lower(): t for t in tags}
    triggers = {str(t) for t in (firing_trigger_ids or [])}

    identifiers, events = _candidate_identity(config, constants, tags_by_name)
    conflicts: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    accounted: set[str] = set()

    def add(kind, blocking, headline, why, entries):
        for entry in entries:
            accounted.add(str(entry["tagId"]))
        (conflicts if blocking else advisory).append(
            {
                "kind": kind,
                "blocking": blocking,
                "headline": headline,
                "why": why,
                "tags": entries,
            }
        )

    # --- 1. The account is already initialised ----------------------------
    for match in _equivalents_in(tag_type, config, tags, context):
        add(
            "initialisation",
            True,
            f"{match['identity']} is already configured by an existing tag",
            "A second initialisation loads the library twice and duplicates "
            "every automatic hit. It is only safe when the two triggers are "
            "mutually exclusive -- different domains or environments.",
            [match],
        )

    by_product = _initialisations_by_product(tags, context)

    # --- 2. A base tag already sends this event ---------------------------
    sends_a_page_view = bool(events & _PAGE_VIEW_EVENTS)
    if tag_type in ("html", "img") and not sends_a_page_view:
        body = _body_of(config)
        # Only when the script does NOT initialise: a full base snippet fires
        # its own page view, but that is already an initialisation and saying
        # it twice helps nobody.
        sends_a_page_view = bool(
            _HTML_PAGE_VIEW.search(body) and not find_initialisations(body)
        )

    if sends_a_page_view:
        if tag_type == "gaawe":
            for product in ("google_tag", "ga4_config"):
                for tag, init in by_product.get(product, []):
                    if str(tag.get("tagId")) in accounted:
                        continue
                    # The destination is often a lookup table rather than a
                    # literal. Matching only literals let a page_view tag be
                    # created for a property the routed Google Tag already
                    # covers -- the tag reported no conflict at all.
                    covered = _possible_values(init.account, constants, candidates)
                    matched = covered & identifiers
                    if not matched:
                        continue
                    if not _sends_its_own_page_view(tag, constants, settings_vars):
                        continue
                    routed = init.account not in matched
                    add(
                        "already_sent_by_a_base_tag",
                        True,
                        f"{', '.join(sorted(matched))} already sends page_view "
                        "automatically"
                        + (f" (via {init.account})" if routed else ""),
                        "A Google Tag sends `page_view` to its destination on "
                        "its own -- that is what configuring the destination "
                        "means. A GA4 Event tag named page_view for the same "
                        "measurement id counts every page view twice, in every "
                        "report in the property. It is the right tag to create "
                        "only when the base tag has send_page_view set to "
                        "false, which this one does not."
                        + (
                            " This base tag reaches the property through a "
                            "lookup table, so it covers it on the pages the "
                            "table matches -- confirm which pages each tag "
                            "should serve."
                            if routed
                            else ""
                        ),
                        [_entry(tag, identity=init.label)],
                    )
        else:
            platform = _candidate_platform(tag_type, config, context)
            for tag, init in by_product.get(platform or "", []):
                if str(tag.get("tagId")) in accounted:
                    continue
                add(
                    "already_sent_by_a_base_tag",
                    True,
                    f"{init.label}'s base tag already sends the page view",
                    "A base pixel fires its own page view when it loads. A "
                    "separate page-view event tag for the same account "
                    "duplicates it.",
                    [_entry(tag, identity=init.label)],
                )

    # --- 3. A tag of this type already has this identity ------------------
    identity = _identity_of(tag_type, config, constants, tags_by_name)
    if identity is not None:
        keys = IDENTITY_KEYS.get(tag_type)
        for tag in tags:
            if str(tag.get("tagId")) in accounted or tag.get("type") != tag_type:
                continue
            other = _identity_of(
                tag_type,
                parameters_to_dict(tag.get("parameter")),
                constants,
                tags_by_name,
            )
            if other != identity:
                continue
            detail = (
                f"the parameters that define a {tag_type} tag ({', '.join(keys)})"
                if keys
                else "every parameter"
            )
            # Two GA4 `select_item` tags on different lists, or one Meta
            # Purchase on web and another on a different flow, are identical by
            # configuration and entirely legitimate. The trigger is what
            # separates a copy from a deliberate second placement, so it decides
            # whether this stops the write or merely asks about it.
            overlapping = (
                tag_type in _IDENTITY_ALWAYS_BLOCKS
                or _shares_a_trigger(triggers, tag)
            )
            add(
                "identical_configuration",
                overlapping,
                f"'{tag.get('name')}' already has this exact configuration",
                f"Same tag type and the same value for {detail}. "
                + (
                    "On an overlapping trigger, so everything would be sent "
                    "twice."
                    if overlapping
                    else "On a different trigger, which is legitimate when the "
                    "same measurement belongs on two separate interactions -- "
                    "confirm it is deliberate rather than a forgotten copy."
                ),
                [_entry(tag)],
            )

    # --- 4. The same conversion, native or hand-written -------------------
    wanted_conversions = {
        entry
        for entry in _conversions_of(
            {"type": tag_type, "parameter": [
                {"key": k, "value": v if isinstance(v, str) else str(v)}
                for k, v in config.items()
            ]},
            constants,
            tags_by_name,
        )
    }
    if wanted_conversions:
        for tag in tags:
            if str(tag.get("tagId")) in accounted:
                continue
            shared = wanted_conversions & set(_conversions_of(tag, constants, tags_by_name))
            if not shared:
                continue
            product, values = sorted(shared)[0]
            add(
                "duplicate_conversion",
                True,
                f"{PRODUCT_LABELS.get(product, product)} "
                + " / ".join(v for v in values if v)
                + f" is already sent by '{tag.get('name')}'",
                "The same conversion configuration already exists"
                + (
                    " -- implemented differently, which is how a half-finished "
                    "migration hides one from the other."
                    if tag.get("type") != tag_type
                    else "."
                )
                + " A second one on an overlapping trigger counts the "
                "conversion twice, and Google Ads has no way to tell them "
                "apart.",
                [_entry(tag)],
            )

    # --- 5. An existing tag's id is a lookup that can produce this one ----
    if identifiers:
        # This is `identical_configuration` with a lookup on one side, so it
        # holds to the same standard: the same tag type, and the variable
        # sitting in a parameter that defines that type. Without the second
        # condition, creating a Google Tag reported four "duplicates" of which
        # three were GA4 event tags routing through the same table -- they send
        # to the destination, they do not configure it.
        identity_keys = IDENTITY_KEYS.get(tag_type)
        for tag in tags:
            if str(tag.get("tagId")) in accounted or tag.get("type") != tag_type:
                continue
            readable = _readable(parameters_to_dict(tag.get("parameter")))
            for key, value in readable.items():
                if identity_keys is not None and key not in identity_keys:
                    continue
                if not isinstance(value, str) or not _REFERENCE_ONLY.match(value.strip()):
                    continue
                variable = value.strip()[2:-2].strip()
                if variable in constants:
                    continue  # a constant resolves exactly; rule 1 handled it
                overlap = set(candidates.get(variable, set())) & identifiers
                if not overlap:
                    continue
                # The variable only supplies ONE field. Everything else that
                # identifies the type still has to match, or a page_view tag
                # reports a conflict with every other event tag routed through
                # the same table.
                if identity_keys and not _rest_of_identity_matches(
                    identity_keys, key, config, readable, constants, tags_by_name
                ):
                    continue
                add(
                    "possible_duplicate_via_variable",
                    True,
                    f"'{tag.get('name')}' uses {{{{{variable}}}}}, which can "
                    f"resolve to {', '.join(sorted(overlap))}",
                    "That lookup table lists this id among its outputs, so the "
                    "existing tag already covers this account on the pages the "
                    "table matches. Whether a dedicated tag is still wanted is "
                    "a judgement about routing, not something the container can "
                    "answer -- confirm which pages each should serve.",
                    [_entry(tag, parameter=key, variable=variable)],
                )
                break

    # --- 6. The same hand-written script ----------------------------------
    if tag_type in ("html", "img"):
        from .tag_identity import html_fingerprint

        candidate = {
            "type": tag_type,
            "parameter": [
                {"key": k, "value": v} for k, v in config.items() if isinstance(v, str)
            ],
        }
        fingerprint = html_fingerprint(candidate)
        if fingerprint:
            for tag in tags:
                if str(tag.get("tagId")) in accounted:
                    continue
                if html_fingerprint(tag) == fingerprint:
                    add(
                        "identical_script",
                        True,
                        f"'{tag.get('name')}' carries this exact script",
                        "The two scripts are identical once whitespace and "
                        "variable references are normalised, so whatever this "
                        "one does would happen twice.",
                        [_entry(tag)],
                    )

    # --- 7. This platform already sends this event for this account -------
    platform = _candidate_platform(tag_type, config, context)
    if platform and events and not sends_a_page_view:
        for tag in tags:
            if str(tag.get("tagId")) in accounted:
                continue
            if _candidate_platform(
                tag.get("type", ""), parameters_to_dict(tag.get("parameter")), context
            ) != platform:
                continue
            other_ids, other_events = _candidate_identity(
                parameters_to_dict(tag.get("parameter")), constants, tags_by_name
            )
            if not (events & other_events):
                continue
            if identifiers and other_ids and not (identifiers & other_ids):
                continue  # a different account of the same platform
            overlapping = _shares_a_trigger(triggers, tag)
            add(
                "duplicate_event_for_account",
                overlapping,
                f"{platform_label(platform)} already sends "
                + ", ".join(sorted(events & other_events))
                + f" in '{tag.get('name')}'",
                (
                    "On an overlapping trigger, so the event would be sent "
                    "twice for the same account."
                    if overlapping
                    else "On a different trigger. Legitimate when one event is "
                    "measured on several pages or interactions -- confirm it is "
                    "deliberate rather than a forgotten copy."
                ),
                [_entry(tag)],
            )

    # --- 8. Advisory: the foundation this tag needs -----------------------
    for requirement in _FOUNDATIONS.get(tag_type, ()):
        missing = _foundation_missing(requirement, tags, by_product, identifiers)
        if missing:
            advisory.append(
                {
                    "kind": "missing_prerequisite",
                    "blocking": False,
                    "headline": missing,
                    "why": (
                        "The tag will be created and will look correct, and it "
                        "will send nothing or lose attribution. Run "
                        "check_tagging_prerequisites for the full picture and "
                        "create the missing tag first."
                    ),
                    "tags": [],
                }
            )

    # --- 9. Advisory: a template exists for this platform -----------------
    if tag_type in ("html", "img") and platform:
        installed = [
            t for t, key in context.get("platform_by_type", {}).items() if key == platform
        ]
        if installed:
            advisory.append(
                {
                    "kind": "prefer_template",
                    "blocking": False,
                    "headline": (
                        f"A {platform_label(platform)} template is installed "
                        f"({', '.join(installed)})"
                    ),
                    "why": (
                        "Prefer the template: it is maintained by the vendor, "
                        "validates its own parameters, and respects consent "
                        "settings that hand-written script bypasses. Custom "
                        "HTML is the fallback, not the default."
                    ),
                    "tags": [],
                }
            )

    # --- 10. Advisory: this identifier is used elsewhere ------------------
    for identifier in sorted(identifiers):
        elsewhere = [
            _entry(tag)
            for tag in tags
            if str(tag.get("tagId")) not in accounted
            and _mentions(identifier, _tag_text(tag, constants))
        ]
        if elsewhere:
            advisory.append(
                {
                    "kind": "same_identifier",
                    "blocking": False,
                    "headline": f"{identifier} is already used by {len(elsewhere)} tag(s)",
                    "why": (
                        "Usually legitimate -- one measurement id belongs in "
                        "every GA4 event tag for that property. Listed so the "
                        "identifier can be confirmed as the intended one, and "
                        "because it is found by shape rather than by knowing "
                        "the vendor, which is what makes it work for tools no "
                        "registry names."
                    ),
                    "tags": elsewhere[:10],
                    "total": len(elsewhere),
                }
            )

    blocking = [c for c in conflicts if c["blocking"]]
    advisory += [c for c in conflicts if not c["blocking"]]
    return {
        "clean": not blocking,
        "blocking_conflicts": blocking,
        "advisory": advisory,
        "identifiers_in_payload": sorted(identifiers),
        "events_in_payload": sorted(events),
        "platform": platform,
        "next_step": (
            "Show the user each blocking conflict, say what you would create "
            "anyway, and ASK. Only after they agree, call again with "
            "confirm_duplicate=true. Never set that flag on your own judgement."
            if blocking
            else "No duplication found. Proceed."
        ),
    }


def _rest_of_identity_matches(
    identity_keys: tuple[str, ...],
    variable_key: str,
    config: dict[str, Any],
    existing: dict[str, Any],
    constants: dict[str, str],
    tags_by_name: dict[str, Any],
) -> bool:
    """Do the identity fields other than the variable's own agree?

    A lookup table supplies one field. For `gaawe` that is `measurementId`, and
    `eventName` still has to match: without this check, creating a page_view
    tag reported a conflict with every GA4 event tag routed through the same
    table, whatever event each one sent.
    """
    candidate = _readable(config)
    for other in identity_keys:
        if other == variable_key:
            continue
        left = _resolve(candidate.get(other, ""), constants, tags_by_name).lower()
        right = _resolve(existing.get(other, ""), constants, tags_by_name).lower()
        if left != right:
            return False
    return True


def _foundation_missing(
    requirement: str,
    tags: list[dict[str, Any]],
    by_product: dict[str, list[tuple[dict[str, Any], Any]]],
    identifiers: set[str],
) -> Optional[str]:
    """One sentence naming what is absent, or None when it is present."""
    if requirement == "conversion_linker":
        if not any(
            t.get("type") == "gclidw" and not t.get("paused") for t in tags
        ):
            return (
                "No Conversion Linker in this workspace. Without it Google Ads "
                "and Floodlight cannot read the click id, and conversions are "
                "attributed to the wrong source or not at all."
            )
        return None

    prefix = {"google_ads_destination": "AW-", "ga4_destination": "G-"}[requirement]
    configured = {
        init.account.upper()
        for product in ("google_tag", "ga4_config")
        for _tag, init in by_product.get(product, [])
        if init.account
    }
    if any(account.startswith(prefix) for account in configured):
        return None
    wanted = [i for i in identifiers if i.upper().startswith(prefix)]
    return (
        f"No base tag configures a {prefix} destination"
        + (f" (this tag targets {', '.join(wanted)})" if wanted else "")
        + ". The tag will fire and the destination will never receive it."
    )


def conflicts_with_existing(
    tag_type: str,
    config: dict[str, Any],
    name: str,
    firing_trigger_ids: Optional[list[str]] = None,
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    exclude_tag_id: Optional[str] = None,
) -> dict[str, Any]:
    """`collect_conflicts` against the live workspace. See it for the rules."""
    parent, tags, context = _fetch(account_id, container_id, workspace_id)
    result = collect_conflicts(
        tag_type, config, name, tags, context, exclude_tag_id, firing_trigger_ids
    )
    result["parent"] = parent
    return result


@tool_errors
def preview_tag_conflicts(
    tag_type: str,
    parameters_json: str = "{}",
    name: str = "",
    updating_tag_id: str = "",
    account_id: Optional[str] = None,
    container_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Ask whether a tag you are about to write already exists. Writes nothing.

    `create_tag` and `update_tag` run this check themselves and refuse if they
    find a conflict, so a single tag needs no separate call. This exists for the
    case that matters more: **planning several tags at once.** Survey the whole
    plan first, present everything that already exists in one message, and let
    the user decide before any of it is written -- rather than discovering the
    third tag is a duplicate after two were created.

    Args:
        tag_type: the API tag type you intend to use ("gaawe", "googtag",
            "awct", "flc", "html", "cvt_..." and so on).
        parameters_json: the parameters you intend to pass, as a JSON string --
            the same value you would give `create_tag`.
        name: the intended tag name. Optional; the comparison is by
            configuration, never by name.
        updating_tag_id: when previewing an UPDATE, the id of the tag being
            edited. It is excluded from the comparison -- without it a tag
            always conflicts with itself.
        account_id: account id. Falls back to the .env value.
        container_id: container id. Falls back to the .env value.
        workspace_id: workspace id. Falls back to the .env value.

    Returns:
        `clean`, `blocking_conflicts` (each naming the existing tags and why it
        matters), `advisory` and `next_step`.
    """
    config = json.loads(parameters_json or "{}")
    if not isinstance(config, dict):
        raise ValueError("parameters_json must be a JSON object")
    return conflicts_with_existing(
        tag_type,
        config,
        name,
        None,
        account_id,
        container_id,
        workspace_id,
        exclude_tag_id=updating_tag_id or None,
    )
