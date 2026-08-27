# Event dictionary - <BUSINESS NAME>

> Version 1.0 - updated <YYYY-MM-DD> - owner: <NAME>
> Platform: GA4 (property <G-XXXXXXX>) | GTM container: <GTM-XXXXXXX>

## Convention

- Event names in `snake_case`, up to 40 characters.
- Google's recommended events take priority over custom ones.
- Every custom event needs a justification on this page.

## Foundation

| Event group | Base tag it requires |
| --- | --- |
| GA4 events | Google Tag `<G-XXXXXXX>` |
| Google Ads conversions | Conversion Linker + `<AW-XXXXXXXXX>` |
| Floodlight | Conversion Linker + advertiser `<id>` |

## Event index

| Event | Category | Source | Priority |
| --- | --- | --- | --- |
| `<event>` | ecommerce / lead / engagement | dataLayer / GTM auto-event | critical / high / medium |

---

## `<event_name>`

**What it measures (business).** <one sentence>

**When it fires (technical).** <dataLayer event, URL, CSS selector, condition>

**When it does NOT fire.** <edge cases that have caused duplicate data before>

**Parameters**

| Parameter | Type | Required | Source | Example |
| --- | --- | --- | --- | --- |
| `<param>` | string / number / boolean | yes / no | `dataLayer.<path>` | `<example>` |

**Custom dimensions and metrics needed in GA4**

| Parameter | Scope | Report name |
| --- | --- | --- |
| `<param>` | event / user | `<name>` |

**dataLayer snippet**

```javascript
dataLayer.push({
  event: "<event_name>",
  // ...
});
```

**Destinations**

| Tool | Action |
| --- | --- |
| GA4 | event `<name>` |
| Google Ads | conversion `<name>` (`AW-XXXX/<label>`) |
| Floodlight | activity `<tag string>` |

**Implementation notes.** <specifics, risks, dependencies>

---

## Open questions

| Item | Who decides | By when |
| --- | --- | --- |
| | | |
