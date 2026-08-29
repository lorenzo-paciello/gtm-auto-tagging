"""Entity specifications and pre-flight validation for the GTM API.

Every rule in this module was verified empirically against the live Tag Manager
API v2 in a throwaway workspace, not inferred from documentation. The API's own
error messages are often misleading -- notably, a `gaawe` tag with a broken
`measurementId` tag reference reports `measurementIdOverride: The value must
not be empty`, pointing at a parameter the caller never touched.

Two failure modes this module exists to prevent:

1. **Opaque 400s.** The agent sends an incomplete payload, gets a
   `vendorTemplate.parameter.X: The value must not be empty` it cannot map back
   to anything it wrote, and retries blindly.
2. **Silent no-ops.** The API *accepts* unknown parameter keys without any
   error. A typo like `measurmentIdOverride` creates a tag that looks correct
   in the UI and does nothing. Only a client-side check catches this.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

#: Parameters that must carry a non-`template` type. The flat JSON the agent
#: writes cannot express these, so they are applied automatically on the way
#: out. `tagReference` values are the *name* of another tag in the workspace.
PARAMETER_TYPE_OVERRIDES: dict[str, dict[str, str]] = {
    "gaawe": {"measurementId": "tagReference"},
    "gaawc": {"measurementId": "tagReference"},
}


@dataclass(frozen=True)
class EntitySpec:
    """What the API demands for one entity type."""

    label: str
    #: Parameters that must be present and non-empty.
    required: tuple[str, ...] = ()
    #: Groups where exactly one member must be present and non-empty.
    one_of: tuple[tuple[str, ...], ...] = ()
    #: Parameters required only when another parameter has a given value.
    conditional: tuple[tuple[str, str, str], ...] = ()  # (if_key, if_value, then_key)
    #: Every parameter key the template understands. Used to catch typos.
    known: tuple[str, ...] = ()
    #: Allowed values for constrained parameters.
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Extra guidance surfaced with the error.
    notes: str = ""
    #: A minimal payload that is known to be accepted.
    example: str = ""


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

TAG_SPECS: dict[str, EntitySpec] = {
    "googtag": EntitySpec(
        label="Google Tag",
        required=("tagId",),
        known=("tagId", "configSettingsTable", "eventSettingsTable", "consentSettings"),
        notes=(
            "`tagId` is the destination: G-XXXXXXX (GA4), AW-XXXXXXXXX (Google "
            "Ads) or GT-XXXXXXX. Prefer a constant variable over a literal."
        ),
        example='{"tagId": "{{CONST - GA4 Measurement ID}}"}',
    ),
    "gaawe": EntitySpec(
        label="Google Analytics: GA4 Event",
        required=("eventName",),
        one_of=(("measurementIdOverride", "measurementId"),),
        known=(
            "eventName",
            "measurementId",
            "measurementIdOverride",
            "eventSettingsTable",
            "eventSettingsVariable",
            "eventParameters",
            "userProperties",
            "sendEcommerceData",
            "getEcommerceDataFrom",
            "ecommerceMacroData",
            "enhancedUserId",
            "userDataVariable",
            "consentSettings",
        ),
        enums={"getEcommerceDataFrom": ("dataLayer", "customObject")},
        notes=(
            "A GA4 Event tag needs a measurement destination, supplied one of "
            "two ways and never both:\n"
            "  - `measurementIdOverride`: a literal G-XXXXXXX or a "
            "{{variable}} reference. Simplest, and what you want in most cases.\n"
            "  - `measurementId`: the NAME of an existing Google Tag in this "
            "workspace. It is sent as a `tagReference`, which this tool applies "
            "for you.\n"
            "The API reports BOTH failures as `measurementIdOverride: The value "
            "must not be empty`, including the case where `measurementId` names "
            "a tag that does not exist. If you hit that error while passing "
            "`measurementId`, the tag name is wrong -- check `list_tags`."
        ),
        example=(
            '{"eventName": "purchase", "measurementIdOverride": '
            '"{{CONST - GA4 Measurement ID}}", "sendEcommerceData": true, '
            '"getEcommerceDataFrom": "dataLayer"}'
        ),
    ),
    "gaawc": EntitySpec(
        label="Google Analytics: GA4 Configuration (legacy)",
        required=("measurementId",),
        known=("measurementId", "fieldsToSet", "userProperties", "consentSettings"),
        notes="Legacy. Prefer `googtag` for new containers.",
        example='{"measurementId": "{{CONST - GA4 Measurement ID}}"}',
    ),
    "awct": EntitySpec(
        label="Google Ads Conversion Tracking",
        required=("conversionId", "conversionLabel"),
        known=(
            "conversionId",
            "conversionLabel",
            "conversionValue",
            "currencyCode",
            "orderId",
            "enableProductReporting",
            "merchantId",
            "itemsByDataLayer",
            "enableShippingData",
            "enableNewCustomerReporting",
            "enableEnhancedConversion",
            "userDataVariable",
            "rdp",
            "consentSettings",
        ),
        notes=(
            "`conversionId` is the digits only from AW-XXXXXXXXX. Always set "
            "`orderId` on purchase conversions: without it a page refresh "
            "counts the conversion again. Requires a Conversion Linker in the "
            "container."
        ),
        example=(
            '{"conversionId": "{{CONST - Google Ads Conversion ID}}", '
            '"conversionLabel": "AbC-D_efG-h12", "conversionValue": '
            '"{{DLV - ecommerce.value}}", "currencyCode": "USD", "orderId": '
            '"{{DLV - ecommerce.transaction_id}}"}'
        ),
    ),
    "sp": EntitySpec(
        label="Google Ads Remarketing",
        required=("conversionId",),
        known=(
            "conversionId",
            "conversionLabel",
            "customParams",
            "enableDynamicRemarketing",
            "eventName",
            "eventValue",
            "userDataVariable",
            "rdp",
            "consentSettings",
        ),
        example='{"conversionId": "{{CONST - Google Ads Conversion ID}}"}',
    ),
    "gclidw": EntitySpec(
        label="Conversion Linker",
        known=(
            "enableCrossDomain",
            "acceptIncoming",
            "linkerDomains",
            "decorateFormsAutoLink",
            "urlPosition",
            "cookiePrefix",
            "enableCookieOverrides",
            "cookieDomain",
            "cookieExpiration",
            "consentSettings",
        ),
        notes=(
            "Takes no required parameters. Fire it on Initialization - All "
            "Pages (2147479573) so it runs before any conversion tag."
        ),
        example="{}",
    ),
    "flc": EntitySpec(
        label="Floodlight Counter",
        required=("advertiserId", "groupTag", "activityTag", "ordinalType"),
        conditional=(("ordinalType", "SESSION", "sessionId"),),
        known=(
            "advertiserId",
            "groupTag",
            "activityTag",
            "ordinalType",
            "sessionId",
            "countingMethod",
            "customVariable",
            "enableGoogleAttributionOptions",
            "attributionOptionImage",
            "enableConversionLinker",
            "conversionCookiePrefix",
            "consentSettings",
        ),
        enums={"ordinalType": ("STANDARD", "UNIQUE", "SESSION")},
        notes=(
            "`ordinalType` is required and easy to miss -- it is not shown as "
            "a separate field in the GTM UI. Use STANDARD for every-time "
            "counting, UNIQUE for once per user per day, SESSION (which then "
            "also requires `sessionId`) for once per session.\n"
            "WARNING: the API accepts an invalid `ordinalType` string without "
            "complaint and the tag then misbehaves at runtime, so this tool "
            "rejects values outside the enum."
        ),
        example=(
            '{"advertiserId": "1234567", "groupTag": "lead", "activityTag": '
            '"contact0", "ordinalType": "STANDARD"}'
        ),
    ),
    "fls": EntitySpec(
        label="Floodlight Sales",
        required=("advertiserId", "groupTag", "activityTag", "revenue", "orderId"),
        known=(
            "advertiserId",
            "groupTag",
            "activityTag",
            "revenue",
            "orderId",
            "quantity",
            "countingMethod",
            "customVariable",
            "enableConversionLinker",
            "conversionCookiePrefix",
            "consentSettings",
        ),
        enums={"countingMethod": ("TRANSACTIONS", "ITEMS_SOLD")},
        notes=(
            "`revenue` and `orderId` are both required by the API. An empty "
            "`orderId` makes CM360 count every page refresh as a new sale."
        ),
        example=(
            '{"advertiserId": "1234567", "groupTag": "purchase", "activityTag": '
            '"trans0", "revenue": "{{DLV - ecommerce.value}}", "orderId": '
            '"{{DLV - ecommerce.transaction_id}}", "countingMethod": "TRANSACTIONS"}'
        ),
    ),
    "html": EntitySpec(
        label="Custom HTML",
        required=("html",),
        known=("html", "supportDocumentWrite", "consentSettings"),
        notes="Last resort. Justify it in `notes` whenever you use it.",
        example='{"html": "<script>console.log(1)</script>"}',
    ),
    "img": EntitySpec(
        label="Custom Image Pixel",
        required=("url",),
        known=("url", "useCacheBuster", "cacheBusterQueryParam", "consentSettings"),
        example='{"url": "https://example.com/pixel.gif"}',
    ),
}


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

VARIABLE_SPECS: dict[str, EntitySpec] = {
    "v": EntitySpec(
        label="Data Layer Variable",
        required=("name",),
        known=("name", "dataLayerVersion", "setDefaultValue", "defaultValue"),
        notes=(
            "`name` is the dataLayer path, e.g. `ecommerce.value`. Always set "
            "`dataLayerVersion` to 2 -- version 1 cannot read dotted paths."
        ),
        example='{"name": "ecommerce.transaction_id", "dataLayerVersion": 2}',
    ),
    "c": EntitySpec(
        label="Constant",
        required=("value",),
        known=("value",),
        example='{"value": "G-XXXXXXXXXX"}',
    ),
    "jsm": EntitySpec(
        label="Custom JavaScript",
        required=("javascript",),
        known=("javascript",),
        notes="Must be an anonymous function that returns a value.",
        example='{"javascript": "function() {\\n  return document.title;\\n}"}',
    ),
    "j": EntitySpec(
        label="JavaScript Variable",
        required=("name",),
        known=("name",),
        example='{"name": "document.title"}',
    ),
    "k": EntitySpec(
        label="1st Party Cookie",
        required=("name",),
        known=("name", "decodeCookie"),
        example='{"name": "_ga"}',
    ),
    "u": EntitySpec(
        label="URL",
        known=("component", "queryKey", "customUrlSource", "stripWWW", "defaultPages"),
        enums={"component": ("URL", "PROTOCOL", "HOST", "PORT", "PATH", "QUERY", "FRAGMENT", "IS_OUTBOUND")},
        notes="Defaults to the full URL when `component` is omitted.",
        example='{"component": "QUERY", "queryKey": "utm_source"}',
    ),
    "d": EntitySpec(
        label="DOM Element",
        known=("selectorType", "elementId", "elementSelector", "attributeName"),
        enums={"selectorType": ("ID", "CSS")},
        example='{"selectorType": "CSS", "elementSelector": ".price", "attributeName": "data-value"}',
    ),
    "smm": EntitySpec(
        label="Lookup Table",
        known=("input", "map", "defaultValue", "setDefaultValue"),
        notes=(
            "`map` is a list of objects with `key` and `value`. Creating one "
            "with no parameters succeeds but produces a variable that always "
            "returns undefined."
        ),
        example=(
            '{"input": "{{Page Hostname}}", "defaultValue": "production", '
            '"map": [{"key": "staging.example.com", "value": "staging"}]}'
        ),
    ),
    "remm": EntitySpec(
        label="RegEx Table",
        known=("input", "map", "defaultValue", "setDefaultValue", "fullMatch", "ignoreCase"),
        example='{"input": "{{Page Path}}", "map": [{"key": "^/blog", "value": "blog"}]}',
    ),
    "aev": EntitySpec(
        label="Auto-Event Variable",
        known=("varType", "attribute", "defaultValue", "setDefaultValue"),
        enums={
            "varType": ("ELEMENT", "CLASSES", "ID", "TARGET", "TEXT", "URL", "ATTRIBUTE", "HISTORY_NEW_URL_FRAGMENT", "HISTORY_OLD_URL_FRAGMENT", "HISTORY_CHANGE_SOURCE")
        },
        example='{"varType": "TEXT"}',
    ),
    "e": EntitySpec(label="Custom Event", notes="Returns the dataLayer event name. No parameters."),
    "r": EntitySpec(label="Random Number"),
    "ctv": EntitySpec(label="Container Version Number"),
    "dbg": EntitySpec(label="Debug Mode"),
    "f": EntitySpec(
        label="HTTP Referrer",
        known=("component", "stripWWW", "queryKey"),
        enums={"component": ("URL", "PROTOCOL", "HOST", "PORT", "PATH", "QUERY", "FRAGMENT")},
    ),
}


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

TRIGGER_TYPES = {
    "pageview",
    "domReady",
    "windowLoaded",
    "init",
    "consentInit",
    "customEvent",
    "click",
    "linkClick",
    "formSubmission",
    "elementVisibility",
    "scrollDepth",
    "timer",
    "historyChange",
    "jsError",
    "youTubeVideo",
    "triggerGroup",
    "always",
    "serverPageview",
}

FILTER_OPERATORS = {
    "equals",
    "contains",
    "startsWith",
    "endsWith",
    "matchRegex",
    "matchCssSelector",
    "urlMatches",
    "greater",
    "greaterOrEquals",
    "less",
    "lessOrEquals",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_entity(
    kind: str, entity_type: str, config: dict[str, Any]
) -> list[dict[str, str]]:
    """Check a payload against the spec before it reaches the API.

    Args:
        kind: "tag" or "variable".
        entity_type: the API type, e.g. "gaawe".
        config: the flat parameter dictionary.

    Returns:
        A list of problems. Each has `severity` ("error" or "warning"),
        `message` and `fix`. An empty list means the payload should be accepted.
    """
    specs = TAG_SPECS if kind == "tag" else VARIABLE_SPECS
    spec = specs.get(entity_type)
    problems: list[dict[str, str]] = []

    if spec is None:
        # Community templates (cvt_*) and anything not in the registry: the
        # parameter surface is defined by the template author, so we cannot
        # validate it. Say so rather than pretend the payload is fine.
        if not entity_type.startswith("cvt_"):
            problems.append(
                {
                    "severity": "warning",
                    "message": f"Unknown {kind} type '{entity_type}'; no spec to validate against.",
                    "fix": (
                        "Confirm the type with `get_entity_spec`. For a "
                        "community template, do not build the type by hand: "
                        "copy the `tag_type` field from `list_templates` "
                        "verbatim. A gallery template uses "
                        "cvt_<galleryTemplateId>; only a hand-written custom "
                        "template uses cvt_<containerId>_<templateId>."
                    ),
                }
            )
        return problems

    for key in spec.required:
        if _is_empty(config.get(key)):
            problems.append(
                {
                    "severity": "error",
                    "message": f"`{key}` is required by {spec.label} and is missing or empty.",
                    "fix": f"Add \"{key}\" to parameters_json. Example: {spec.example}",
                }
            )

    for group in spec.one_of:
        present = [k for k in group if not _is_empty(config.get(k))]
        if not present:
            problems.append(
                {
                    "severity": "error",
                    "message": (
                        f"{spec.label} requires exactly one of: "
                        + ", ".join(f"`{k}`" for k in group)
                        + ". None was provided."
                    ),
                    "fix": f"{spec.notes}\nExample: {spec.example}",
                }
            )
        elif len(present) > 1:
            problems.append(
                {
                    "severity": "error",
                    "message": (
                        f"{spec.label} accepts only one of "
                        + ", ".join(f"`{k}`" for k in group)
                        + f", but got {len(present)}: {', '.join(present)}."
                    ),
                    "fix": f"Remove all but one. {spec.notes}",
                }
            )

    for if_key, if_value, then_key in spec.conditional:
        if str(config.get(if_key, "")).upper() == if_value and _is_empty(config.get(then_key)):
            problems.append(
                {
                    "severity": "error",
                    "message": f"`{then_key}` is required when `{if_key}` is {if_value}.",
                    "fix": f'Add "{then_key}" to parameters_json, or choose a different {if_key}.',
                }
            )

    for key, allowed in spec.enums.items():
        value = config.get(key)
        if value is not None and str(value) not in allowed:
            problems.append(
                {
                    "severity": "error",
                    "message": f"`{key}` = {value!r} is not a valid value.",
                    "fix": "Use one of: " + ", ".join(allowed),
                }
            )

    if spec.known:
        unknown = [k for k in config if k not in spec.known]
        if unknown:
            problems.append(
                {
                    "severity": "warning",
                    "message": (
                        f"{spec.label} does not recognise: "
                        + ", ".join(f"`{k}`" for k in unknown)
                        + "."
                    ),
                    "fix": (
                        "The API accepts unknown parameter keys WITHOUT an "
                        "error, and they do nothing at runtime -- this is "
                        "usually a typo. Known keys: "
                        + ", ".join(spec.known)
                    ),
                }
            )

    return problems


def format_problems(
    kind: str, entity_type: str, problems: list[dict[str, str]]
) -> dict[str, Any]:
    """Turn validation problems into an error payload the model can act on."""
    errors = [p for p in problems if p["severity"] == "error"]
    spec = (TAG_SPECS if kind == "tag" else VARIABLE_SPECS).get(entity_type)
    return {
        "error": "invalid_parameters",
        "entity_type": entity_type,
        "label": spec.label if spec else entity_type,
        "message": (
            f"The payload would be rejected by the GTM API "
            f"({len(errors)} problem{'s' if len(errors) != 1 else ''}). "
            "Nothing was sent."
        ),
        "problems": problems,
        "required": list(spec.required) if spec else [],
        "one_of": [list(g) for g in spec.one_of] if spec else [],
        "example_parameters_json": spec.example if spec else "",
        "notes": spec.notes if spec else "",
    }


def get_entity_spec(kind: str = "tag", entity_type: str = "") -> dict[str, Any]:
    """Look up what the GTM API requires for a tag or variable type.

    Call this BEFORE building `parameters_json` when you are unsure which
    parameters a type needs. It is cheaper than a failed API round trip and the
    API's own error messages are misleading for several types.

    Args:
        kind: "tag" or "variable".
        entity_type: the API type, e.g. "gaawe", "flc", "v". Leave empty to
            list every type this project knows about.

    Returns:
        The specification: required parameters, mutually exclusive groups,
        allowed values, every recognised parameter key, and a working example.
    """
    kind = (kind or "tag").strip().lower()
    if kind not in ("tag", "variable"):
        return {
            "error": "invalid_arguments",
            "message": "kind must be 'tag' or 'variable'.",
        }

    specs = TAG_SPECS if kind == "tag" else VARIABLE_SPECS

    if not entity_type.strip():
        return {
            "kind": kind,
            "available_types": {t: s.label for t, s in specs.items()},
            "note": "Call again with entity_type set for the full specification.",
        }

    spec = specs.get(entity_type.strip())
    if spec is None:
        return {
            "error": "unknown_type",
            "message": f"No spec for {kind} type '{entity_type}'.",
            "available_types": {t: s.label for t, s in specs.items()},
            "hint": (
                "Community template types come from `list_templates` -- copy "
                "the `tag_type` field verbatim rather than assembling it. A "
                "gallery template uses cvt_<galleryTemplateId>; a hand-written "
                "custom template uses cvt_<containerId>_<templateId>."
            ),
        }

    return {
        "kind": kind,
        "type": entity_type,
        "label": spec.label,
        "required_parameters": list(spec.required),
        "exactly_one_of": [list(g) for g in spec.one_of],
        "conditionally_required": [
            {"when": f"{k} == {v}", "then_required": t} for k, v, t in spec.conditional
        ],
        "allowed_values": {k: list(v) for k, v in spec.enums.items()},
        "all_known_parameters": list(spec.known),
        "notes": spec.notes,
        "example_parameters_json": spec.example,
    }
