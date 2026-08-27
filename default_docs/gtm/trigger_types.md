# GTM - trigger types in the API v2

| `type` | UI name | Notes |
| --- | --- | --- |
| `pageview` | Page View | fires at the start of the page load |
| `domReady` | DOM Ready | |
| `windowLoaded` | Window Loaded | |
| `init` | Initialization | before any page view |
| `consentInit` | Consent Initialization | first of all; use it for the CMP |
| `customEvent` | Custom Event | reads `event` from the dataLayer |
| `click` | Click - All Elements | needs the click built-in variables |
| `linkClick` | Click - Just Links | has `waitForTags` and `checkValidation` |
| `formSubmission` | Form Submission | same |
| `elementVisibility` | Element Visibility | `selectorType`, `elementId`/`elementSelector`, `firingFrequency` |
| `scrollDepth` | Scroll Depth | `verticalThresholdUnits`, `verticalThresholdsPercent` |
| `timer` | Timer | `interval`, `limit` |
| `historyChange` | History Change | SPA |
| `jsError` | JavaScript Error | |
| `youTubeVideo` | YouTube Video | `captureStart`, `captureComplete`, `captureProgress`, `progressThresholdsPercent` |
| `triggerGroup` | Trigger Group | `triggerIds` |
| `always` | All Pages (no condition) | |
| `serverPageview` | Client Request (server-side container) | |

## Reserved built-in triggers

Three triggers live outside the workspace collection. `list_triggers` never
returns them, but their ids are valid `firingTriggerId` values:

| Id | Name | Type |
| --- | --- | --- |
| `2147479553` | All Pages | `pageview` |
| `2147479572` | Consent Initialization - All Pages | `consentInit` |
| `2147479573` | Initialization - All Pages | `init` |

Retrieve them with `list_built_in_triggers()`. **Never create a duplicate "All
Pages" trigger.**

## Filters

A trigger has two condition lists:

- `customEventFilter` - only for `customEvent`: compares `{{_event}}` against
  the event name.
- `filter` - additional "fire when..." conditions, applied to any type.

`create_trigger` builds both for you:

```
create_trigger(
  name="CE - purchase",
  trigger_type="customEvent",
  custom_event_name="purchase",
  filters_json='[{"variable": "Page Path", "operator": "contains", "value": "/checkout/success"}]'
)
```

### Valid operators

| Operator | Meaning |
| --- | --- |
| `equals` | equals |
| `contains` | contains |
| `startsWith` | starts with |
| `endsWith` | ends with |
| `matchRegex` | matches regex |
| `matchCssSelector` | matches CSS selector |
| `urlMatches` | matches URL |
| `greater`, `greaterOrEquals` | greater than, greater or equal |
| `less`, `lessOrEquals` | less than, less or equal |

Each operator has a negated counterpart in the UI ("does not contain"); on the
API that is expressed by the filter's `negate` field.

## Project standards

1. **Prefer `customEvent`** whenever the data comes from the dataLayer. A click
   trigger based on text or CSS class breaks with the first layout change.
2. **One trigger per business event**, reused by every tag that needs it (GA4,
   Google Ads, Floodlight, Meta). Do not create `CE - purchase (GA4)` and
   `CE - purchase (Ads)`.
3. **`elementVisibility`** for banners and sections; set `firingFrequency` to
   "once per page" unless the requirement says otherwise.
4. **Blocking**: use `blockingTriggerId` instead of encoding exceptions in tag
   names. e.g. an `EXC - Staging environment` trigger that blocks advertising
   tags when the hostname is a staging host.
5. Name them per `conventions/naming_conventions.md` (`CE - purchase`,
   `PV - Checkout`, `CLK - Buy button`).

## Required built-in variables

Some triggers do not work unless the matching built-in variables are enabled.
Check with `list_built_in_variables`:

| Trigger | Required variables |
| --- | --- |
| `click`, `linkClick` | Click Element, Click Classes, Click ID, Click Text, Click URL |
| `formSubmission` | Form Element, Form Classes, Form ID, Form Target, Form URL, Form Text |
| `elementVisibility` | Percent Visible, On-Screen Duration |
| `scrollDepth` | Scroll Depth Threshold, Scroll Depth Units, Scroll Direction |
| `youTubeVideo` | Video Provider, Video Status, Video Title, Video Percent |
| `historyChange` | History Source, New History Fragment, Old History Fragment |
