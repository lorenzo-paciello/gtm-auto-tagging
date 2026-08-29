"""Recognising a vendor pixel inside hand-written script.

This is the matching engine. The platforms themselves live in one place --
`media_platforms.MEDIA_PLATFORMS` -- so the prerequisite check, the media
listing, the identity audit and duplicate detection all recognise the same set
of vendors. Two registries drifted apart once already: a container was told its
Taboola pixel was installed twice while the creator agent had never heard of
Taboola.

## Initialisation, not events

Duplication only matters at the base tag. Most platforms carry the account id
in exactly one place -- the initialisation call -- and their event tags simply
use whatever library that call loaded:

    fbq('init', '123')            <- the account lives here
    fbq('track', 'AddToCart')     <- no account; uses the pixel above

So comparing every tag by `(account, event)` produces noise, not findings:
twenty GA4 tags firing `click` on different pages are twenty legitimate tags.
The question worth asking is narrower: **is this account initialised more than
once?** Two initialisations of one pixel double every hit on the site.

Some vendors repeat the account id in every call -- Taboola's event push
carries `id:`, Kakao's conversion call is `kakaoPixel(id).purchase()`. For
those, `events_repeat_the_id` makes an event match veto the init match, so
their conversion tags do not all read as duplicate base pixels.

## Coverage

Two mechanisms, because no fixed list covers every container:

1. Explicit `init` patterns per platform. Each captures the account id.
2. `script_fingerprint` -- for a vendor in no registry, two Custom HTML tags
   whose scripts are the same modulo whitespace and GTM variables are still a
   duplicate. This is what covers the platform nobody anticipated.

The explicit table earns its keep by supplying the account id: without it, two
base tags for *different* accounts of the same vendor would look identical to
the fingerprint.

## One rule that must stay true

**Match the raw parameter value, never a JSON dump.** `json.dumps` escapes `"`
as `\\"`, so a double-quoted snippet stops matching -- which once hid every
LinkedIn tag in a container while Meta kept working, purely because Meta's
snippet uses single quotes.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from .media_platforms import MEDIA_PLATFORMS

def _first_capturing_group(pattern: str) -> Optional[int]:
    """Index of the account-id group's opening paren, skipping `(?:...)`."""
    in_class = False
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(" and not pattern.startswith("(?", index):
            return index
        index += 1
    return None


def _closing_paren(pattern: str, start: int) -> int:
    depth = 0
    in_class = False
    index = start
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"unbalanced parentheses in {pattern!r}")


def _accepts_a_gtm_variable(pattern: str) -> str:
    """Widen a pattern's account-id group to also accept `{{Variable}}`.

    A hand-written pixel usually parameterises its id --
    `fbq('init', '{{CONST - Meta Pixel ID}}')` is the normal way to write one
    in Tag Manager -- and a pattern that only accepts digits misses every one
    of them, which is half the hand-written pixels in a governed container.

    Done here rather than in the registry so each entry states the literal id
    shape and nothing else. `initialisations_of` then resolves the constant, so
    a Custom HTML pixel using `{{CONST - Pixel ID}}` and a template tag holding
    the literal value compare as the same account.
    """
    start = _first_capturing_group(pattern)
    if start is None:
        return pattern
    end = _closing_paren(pattern, start)
    inner = pattern[start + 1 : end]
    return pattern[:start] + "((?:" + inner + r")|\{\{[^{}]+\}\})" + pattern[end + 1 :]


_INIT = {
    key: [
        re.compile(_accepts_a_gtm_variable(p), re.IGNORECASE) for p in platform.init
    ]
    for key, platform in MEDIA_PLATFORMS.items()
}
_EVENTS = {
    key: [re.compile(p, re.IGNORECASE) for p in platform.events]
    for key, platform in MEDIA_PLATFORMS.items()
}


def platform_label(key: str) -> str:
    platform = MEDIA_PLATFORMS.get(key)
    return platform.label if platform else key


def _excerpt(matched: str) -> str:
    collapsed = " ".join(matched.split())
    return collapsed if len(collapsed) <= 48 else collapsed[:45] + "..."


def init_signal(key: str, text: str) -> Optional[str]:
    """A human-readable description of the initialisation found, or None.

    Used as a STRONG detection signal: a vendor's own init call in a Custom
    HTML body attributes the tag to that vendor beyond doubt.
    """
    for pattern in _INIT.get(key, []):
        match = pattern.search(text)
        if match:
            return f"initialisation call ({_excerpt(match.group(0))})"
    return None


def event_signal(key: str, text: str) -> Optional[str]:
    """A description of the event call found, or None."""
    for pattern in _EVENTS.get(key, []):
        match = pattern.search(text)
        if match:
            return f"event call ({_excerpt(match.group(0))})"
    return None


def find_initialisations(text: str) -> list[tuple[str, str]]:
    """Return `(platform, account_id)` for every pixel INITIALISED in the text.

    An event call is deliberately not a match: `fbq('track', ...)` uses a pixel
    initialised elsewhere and configures no account of its own. For a vendor
    that repeats its id in every call, an event match vetoes the init match --
    otherwise its conversion tags all read as duplicate base pixels.
    """
    found: list[tuple[str, str]] = []
    for key, patterns in _INIT.items():
        if MEDIA_PLATFORMS[key].events_repeat_the_id and any(
            p.search(text) for p in _EVENTS.get(key, [])
        ):
            continue
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                found.append((key, match.group(1)))
                break
    return found


def find_event_only_platforms(text: str) -> list[str]:
    """Platforms present only through an event call, with no initialisation.

    Such a tag is not a base tag and cannot duplicate one. It is still worth
    surfacing in an audit: it breaks outright if the pixel it depends on is
    removed.
    """
    initialised = {key for key, _ in find_initialisations(text)}
    return [
        key
        for key, patterns in _EVENTS.items()
        if key not in initialised and any(p.search(text) for p in patterns)
    ]


#: GTM variable references differ between two copies of one script without
#: making them different scripts.
_VARIABLE = re.compile(r"\{\{[^{}]*\}\}")
#: Block comments only. A line comment cannot be stripped safely: `//` also
#: opens a protocol-relative URL (`//cdn.vendor.io/p.js`), and every pixel
#: snippet loads a script from a CDN. Stripping it eats the rest of the line
#: and collapses the fingerprint to nothing. Two copies of one snippet carry
#: the same comments anyway.
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_WHITESPACE = re.compile(r"\s+")


def script_fingerprint(text: str) -> Optional[str]:
    """A stable hash of a script's structure, for vendors we cannot name.

    Normalises away comments, whitespace and `{{Variable}}` references, so two
    Custom HTML tags carrying the same snippet fingerprint alike even when one
    was reformatted or parameterised. Returns None for anything too short to
    be a meaningful pixel.

    This is what covers the platform nobody anticipated -- a container in the
    wild carries far more vendors than any fixed list.
    """
    if not text:
        return None
    normalised = _BLOCK_COMMENT.sub("", text)
    normalised = _VARIABLE.sub("{}", normalised)
    # Whitespace is removed entirely, not collapsed: one copy of a snippet may
    # be minified and another pretty-printed, and a single space between
    # statements would still make them differ.
    normalised = _WHITESPACE.sub("", normalised).lower()
    if len(normalised) < 120:
        return None
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:16]
