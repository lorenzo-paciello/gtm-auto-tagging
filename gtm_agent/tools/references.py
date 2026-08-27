"""Validation of `{{Variable}}` references inside tag and trigger payloads.

GTM resolves `{{Some Name}}` by looking up a variable of that name at runtime.
If none exists the reference resolves to an empty string -- no error, no
warning, nothing in the UI to see. The API accepts the tag happily.

This is how a single agent run produced ten GA4 ecommerce tags all pointing at
`{{CONST - GA4 Measurement ID}}`, a variable that was never created. Every tag
looked correct in the container and none of them would have sent a measurement
id.

Two classes of broken reference, with different fixes:

* the name matches no variable at all -> create the variable first
* the name matches a GTM BUILT-IN variable that is not enabled in this
  container -> enable it; creating a user variable with that name is wrong

The built-in list is derived from the API's own `BuiltInVariable` type enum
rather than a remembered table of display names.
"""

from __future__ import annotations

import functools
import importlib.resources
import json
import re
from typing import Any
from typing import Iterable

#: `{{Name}}`. GTM does not allow nested braces inside a reference.
_REFERENCE_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")

#: Internal names GTM uses in trigger filters and tag configuration. They are
#: never user variables and must not be reported as missing.
RESERVED_REFERENCES = frozenset(
    {
        "_event",
        "_triggers",
        "_url",
        "_cookie",
        "_element",
        "_elementClasses",
        "_elementId",
        "_elementTarget",
        "_elementUrl",
        "_historySource",
        "_newHistoryFragment",
        "_oldHistoryFragment",
        "_newHistoryState",
        "_oldHistoryState",
        "_error",
        "_errorLine",
        "_errorUrl",
        "_referrer",
        "_sequenceIndex",
    }
)


def _normalize(name: str) -> str:
    """Fold a display name and an API enum name onto the same key.

    "Page URL" and `pageUrl` both become `pageurl`, so the enum can be used
    without inventing a table of display strings.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


@functools.lru_cache(maxsize=1)
def built_in_variable_names() -> frozenset[str]:
    """Normalized names of every GTM built-in variable.

    Read from the Tag Manager discovery document that ships with
    google-api-python-client, so the list stays in step with the API instead of
    being a remembered table. Returns an empty set if the document is missing,
    which degrades the message rather than breaking the check.
    """
    try:
        # A namespace package: `__file__` is None, so go through the loader.
        document = (
            importlib.resources.files("googleapiclient.discovery_cache.documents")
            / "tagmanager.v2.json"
        ).read_text(encoding="utf-8")
        schema = json.loads(document)["schemas"]["BuiltInVariable"]
        enum = schema["properties"]["type"]["enum"]
    except Exception:  # pragma: no cover - discovery document unavailable
        return frozenset()
    return frozenset(
        _normalize(value) for value in enum if not value.endswith("Unspecified")
    )


def extract_references(value: Any) -> set[str]:
    """Collect every `{{Name}}` used anywhere inside a payload."""
    if value is None:
        return set()
    blob = value if isinstance(value, str) else json.dumps(value, default=str)
    return {match.strip() for match in _REFERENCE_PATTERN.findall(blob)}


def check_references(
    payload: Any,
    variable_names: Iterable[str],
    enabled_built_ins: Iterable[str],
) -> list[dict[str, str]]:
    """Report `{{Name}}` references that will resolve to an empty string.

    Args:
        payload: anything containing references -- a parameter dict, a string.
        variable_names: user-defined variable names in the workspace.
        enabled_built_ins: display names of the built-in variables enabled here.

    Returns:
        One problem per unresolved reference, each with a `fix` that matches
        the actual cause.
    """
    known = {_normalize(n) for n in variable_names} | {
        _normalize(n) for n in enabled_built_ins
    }
    reserved = {_normalize(n) for n in RESERVED_REFERENCES}
    all_built_ins = built_in_variable_names()

    problems: list[dict[str, str]] = []
    for reference in sorted(extract_references(payload)):
        key = _normalize(reference)
        if key in known or key in reserved:
            continue

        if key in all_built_ins:
            problems.append(
                {
                    "severity": "error",
                    "message": (
                        f"`{{{{{reference}}}}}` is a GTM built-in variable that is "
                        "NOT enabled in this container."
                    ),
                    "fix": (
                        f"Enable the '{reference}' built-in variable in the GTM "
                        "UI (Variables > Configure). Do NOT create a user "
                        "variable with that name -- it would shadow the "
                        "built-in and behave differently. `list_built_in_variables` "
                        "shows what is currently enabled."
                    ),
                }
            )
        else:
            problems.append(
                {
                    "severity": "error",
                    "message": (
                        f"`{{{{{reference}}}}}` does not exist in this workspace. "
                        "GTM resolves an unknown reference to an EMPTY STRING at "
                        "runtime, with no error anywhere."
                    ),
                    "fix": (
                        f"Create the variable first, then create this tag. For a "
                        f"constant: create_variable(name=\"{reference}\", "
                        'variable_type="c", parameters_json=\'{"value": "..."}\'). '
                        "Check `list_variables` for an existing variable with a "
                        "different name."
                    ),
                }
            )
    return problems
