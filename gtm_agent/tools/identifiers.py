"""Destination-identifier consistency across a container.

A tag can carry a perfectly valid measurement id that no base tag ever
configures. GTM accepts it, the tag fires, and the hit goes to a property
nobody is watching -- or nowhere at all. Nothing in the UI compares the two.

Three real failures this module exists to catch, all observed:

1. A GA4 event tag with a literal `G-0987654321` while the container's only
   Google Tag configures `G-1234567890`. Valid format, wrong destination.
2. Two constant variables differing only in case -- `CONST - GA4 Measurement ID`
   and `CONST - GA4 Measurement id`. Creating one fixes half the tags and
   leaves the other half silently empty, because GTM matches variable names
   exactly.
3. A media event tag whose pixel id differs from the one its own base tag uses.

Comparison has to see through variables: the tag says
`{{CONST - GA4 Measurement ID}}`, the variable holds `G-1234567890`, and the
Google Tag holds `G-1234567890`. Constants are resolved before comparing.
"""

from __future__ import annotations

import re
from typing import Any
from typing import Optional

#: Prefixes that identify a Google destination, and what they feed.
GOOGLE_DESTINATION_PREFIXES = {
    "G-": "Google Analytics 4",
    "AW-": "Google Ads",
    "DC-": "Floodlight / Campaign Manager 360",
    "GT-": "Google Tag container",
}

#: Shape of each id, used to flag a value that cannot be a destination at all.
_DESTINATION_PATTERN = re.compile(r"^(G|AW|DC|GT)-[A-Za-z0-9]+$", re.IGNORECASE)

_REFERENCE_PATTERN = re.compile(r"^\{\{([^{}]+)\}\}$")


def _normalize_name(name: str) -> str:
    """Fold a variable name for collision detection only, never for lookup.

    GTM matches variable names byte for byte, so this is used to find names
    that a human would read as the same and GTM would not.
    """
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def constant_values(variables: list[dict[str, Any]]) -> dict[str, str]:
    """Map constant-variable name to its literal value.

    Only `c` (Constant) variables have a value knowable without running the
    container. A data layer variable or custom JavaScript resolves at runtime,
    so its destination cannot be checked statically -- that is reported as
    unknown rather than guessed.
    """
    values: dict[str, str] = {}
    for variable in variables:
        if variable.get("type") != "c":
            continue
        name = variable.get("name")
        value = (variable.get("parameters") or {}).get("value")
        if name and value is not None:
            values[name] = str(value).strip()
    return values


def resolve_value(
    raw: Any, constants: dict[str, str]
) -> tuple[Optional[str], str]:
    """Resolve a parameter value to a literal id where possible.

    Returns:
        `(value, kind)` where kind is "literal", "constant", "unresolved"
        (a reference to a variable that is not a constant) or "missing"
        (a reference to a variable that does not exist).
    """
    if raw is None:
        return None, "missing"
    text = str(raw).strip()
    if not text:
        return None, "missing"

    match = _REFERENCE_PATTERN.match(text)
    if not match:
        return text, "literal"

    name = match.group(1).strip()
    if name in constants:
        return constants[name], "constant"
    return None, "unresolved"


def find_name_collisions(names: list[str]) -> list[dict[str, Any]]:
    """Names that read as the same but that GTM treats as different.

    `CONST - GA4 Measurement ID` and `CONST - GA4 Measurement id` are two
    separate variables. Fixing one leaves the other empty, and the difference
    is invisible at a glance.
    """
    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(_normalize_name(name), []).append(name)

    return [
        {
            "variants": sorted(variants),
            "count": len(variants),
            "why": (
                "GTM matches variable names exactly, so these are separate "
                "variables. A tag referencing one is unaffected by the other."
            ),
        }
        for variants in groups.values()
        if len(set(variants)) > 1
    ]


def classify_destination(value: str) -> Optional[str]:
    """Return the product a destination id belongs to, or None if it is not one."""
    for prefix, product in GOOGLE_DESTINATION_PREFIXES.items():
        if value.upper().startswith(prefix):
            return product
    return None


def looks_like_destination(value: str) -> bool:
    return bool(_DESTINATION_PATTERN.match(value or ""))

def find_near_miss_references(
    references: list[str], variable_names: list[str]
) -> list[dict[str, Any]]:
    """Match an unresolved reference against an existing variable name.

    The observed failure: a container had `CONST - GA4 Measurement ID` and ten
    tags referencing `CONST - GA4 Measurement id`. Creating the first fixed
    nothing for the tags on the second, and "variable not found" alone does not
    tell anyone that the right variable is sitting there one letter away.

    Args:
        references: names that did not resolve.
        variable_names: variables that do exist in the workspace.

    Returns:
        One entry per reference that has a near-identical existing variable.
    """
    by_key: dict[str, list[str]] = {}
    for name in variable_names:
        by_key.setdefault(_normalize_name(name), []).append(name)

    matches = []
    for reference in references:
        candidates = by_key.get(_normalize_name(reference), [])
        candidates = [c for c in candidates if c != reference]
        if candidates:
            matches.append(
                {
                    "reference": reference,
                    "existing": sorted(candidates),
                    "why": (
                        "These differ only in case or punctuation. GTM matches "
                        "variable names exactly, so the reference resolves to "
                        "an empty string while the real variable sits unused."
                    ),
                }
            )
    return matches



#: Variables that hold a block of tag settings rather than a value. A Google
#: Tag can keep its whole configuration -- `send_page_view` included -- in a
#: `gtcs` variable referenced by `configSettingsVariable`, and a GA4 event its
#: parameters in a `gtes` one. A check that reads only the tag sees an empty
#: settings table and concludes the setting is absent.
_SETTINGS_TYPES = ("gtcs", "gtes")


def settings_variable_values(
    variables: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Settings variable name -> the `name: value` rows it holds."""
    from .gtm_client import setting_values

    return {
        variable["name"]: setting_values(variable.get("parameters") or {})
        for variable in variables
        if variable.get("type") in _SETTINGS_TYPES and variable.get("name")
    }


#: Variable types whose possible outputs can be read without running the
#: container. A lookup table cannot be reduced to one value, but the set of
#: values it can produce is known, and that is enough to ask "could this
#: variable already be carrying the id I am about to add?"
_TABLE_TYPES = ("smm", "remm")


def variable_value_candidates(
    variables: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Every literal value each variable could resolve to.

    `constant_values` answers "what IS this variable" and only Constants can
    answer it. This answers the weaker but far more useful question: "what
    COULD it be?"

    It matters because governed containers route by lookup table. One real
    container has a RegEx table mapping 27 URL patterns to 27 different GA4
    measurement ids, and a single Google Tag whose `tagId` is that variable. A
    check that only resolves Constants sees `{{[ED]ID-Metrica-Estados}}`,
    resolves nothing, and reports a brand-new Google Tag for one of those 27
    ids as perfectly clean -- when the property is already configured.

    A `{{Reference}}` among the outputs is skipped rather than followed: one
    level of indirection is worth reading, a chain of them is guesswork.
    """
    candidates: dict[str, set[str]] = {}
    for variable in variables:
        name = variable.get("name")
        if not name:
            continue
        values: set[str] = set()
        parameters = variable.get("parameters") or {}
        variable_type = variable.get("type")

        if variable_type == "c":
            value = parameters.get("value")
            if value is not None:
                values.add(str(value).strip())
        elif variable_type in _TABLE_TYPES:
            for row in parameters.get("map") or []:
                if isinstance(row, dict):
                    value = row.get("value")
                    if isinstance(value, str) and value.strip():
                        values.add(value.strip())
            default = parameters.get("defaultValue")
            if isinstance(default, str) and default.strip():
                values.add(default.strip())

        values = {v for v in values if not (v.startswith("{{") and v.endswith("}}"))}
        if values:
            candidates[name] = values
    return candidates
