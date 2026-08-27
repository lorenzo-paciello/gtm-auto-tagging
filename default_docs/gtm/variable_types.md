# GTM - variable types in the API v2

| `type` | UI name | Parameters |
| --- | --- | --- |
| `v` | Data Layer Variable | `name` (path, e.g. `ecommerce.value`), `dataLayerVersion` (use `2`), `setDefaultValue`, `defaultValue` |
| `c` | Constant | `value` |
| `jsm` | Custom JavaScript | `javascript` (an anonymous function returning a value) |
| `j` | JavaScript Variable | `name` (a global, e.g. `document.title`) |
| `u` | URL | `component` (`URL`, `HOST`, `PATH`, `QUERY`, `FRAGMENT`, `PROTOCOL`), `queryKey` |
| `f` | HTTP Referrer | `component` |
| `k` | 1st Party Cookie | `name`, `decodeCookie` |
| `d` | DOM Element | `elementId` or `elementSelector`, `attributeName` |
| `e` | Custom Event | no parameters; returns the event name |
| `smm` | Lookup Table | `input`, `map` (list of pairs), `defaultValue` |
| `remm` | RegEx Table | `input`, `map`, `fullMatch`, `ignoreCase` |
| `aev` | Auto-Event Variable | `varType` (`ELEMENT`, `CLASSES`, `ID`, `TARGET`, `TEXT`, `URL`, `ATTRIBUTE`) |
| `r` | Random Number | |
| `ctv` | Container Version Number | |
| `dbg` | Debug Mode | |
| `gtes` | Google Tag: Event Settings | `eventSettingsTable` |
| `gtcs` | Google Tag: Configuration Settings | `configSettingsTable` |

## `parameters_json` examples

### Data Layer Variable

```json
{"name": "ecommerce.transaction_id", "dataLayerVersion": 2}
```

With a default value:

```json
{"name": "user_id", "dataLayerVersion": 2, "setDefaultValue": true, "defaultValue": "(not logged in)"}
```

### Constant

```json
{"value": "G-XXXXXXXXXX"}
```

### URL - query parameter

```json
{"component": "QUERY", "queryKey": "utm_source"}
```

### Lookup table (environment by hostname)

```json
{
  "input": "{{Page Hostname}}",
  "defaultValue": "production",
  "map": [
    {"key": "staging.example.com", "value": "staging"},
    {"key": "localhost", "value": "development"}
  ]
}
```

> On the API, a lookup table is a list of maps with `key` and `value` keys. The
> tool converts the flat JSON automatically.

### Custom JavaScript

```json
{"javascript": "function() {\n  return document.title.trim().toLowerCase();\n}"}
```

## Project rules

1. **Every measurement, conversion or advertiser id becomes a constant.**
   Switching properties must not mean editing ten tags.
2. **Data Layer Variables always with `dataLayerVersion: 2`.** Version 1 does
   not understand dotted paths (`ecommerce.value`).
3. **`jsm` is the last resort.** Custom JavaScript is unauditable for anyone
   who does not read code, and it is the most common source of "ghost"
   variables in an audit. Every `jsm` variable needs `notes` explaining what it
   does.
4. **Never put plain personal data in a variable** that feeds advertising. For
   Enhanced Conversions, use the native `user_data` field or SHA-256 hashing.
5. **Renaming a variable does not update its references.** `{{Old name}}`
   inside tags keeps pointing at a name that no longer exists, and the tag
   starts sending an empty string. List every usage before renaming.

## Recommended built-in variables

Enable at least: Page URL, Page Hostname, Page Path, Referrer, Event, Click
Element, Click Classes, Click ID, Click Text, Click URL, Form Element, Form ID,
Form Classes, Scroll Depth Threshold, Container ID, Debug Mode.
