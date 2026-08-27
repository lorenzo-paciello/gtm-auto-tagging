# Naming conventions - <BUSINESS NAME>

> Version 1.0 - updated <YYYY-MM-DD> - owner: <NAME>

## Principle

The name has to answer, without opening the entity: **which tool**, **what kind
of thing it is**, **what it does**.

## Tags

Format: `<TOOL> - <TYPE> - <DESCRIPTION>`

| Tool | Type | Example |
| --- | --- | --- |
| GA4 | Config, Event | `GA4 - Event - purchase` |
| Google Ads | Conversion, Remarketing, Linker | `Google Ads - Conversion - Lead` |
| Floodlight | Counter, Sales | `Floodlight - Sales - Purchase` |
| <other> | | |

- Right: `GA4 - Event - add_to_cart`
- Wrong: `ga4 add to cart`, `Cart tag`, `GA4_AddToCart`

## Triggers

Format: `<TYPE> - <CONDITION>`

| Type | Prefix | Example |
| --- | --- | --- |
| Custom event | `CE` | `CE - purchase` |
| Page view | `PV` | `PV - Checkout` |
| Element click | `CLK` | `CLK - Buy button` |
| Visibility | `VIS` | `VIS - Home banner` |
| Form submission | `FORM` | `FORM - Contact` |

Built-in triggers (All Pages, Initialization, Consent Initialization) keep their
reserved names.

## Variables

Format: `<TYPE> - <SOURCE>`

| Type | Prefix | Example |
| --- | --- | --- |
| Data Layer Variable | `DLV` | `DLV - ecommerce.transaction_id` |
| Constant | `CONST` | `CONST - GA4 Measurement ID` |
| Custom JavaScript | `CJS` | `CJS - Normalize Email` |
| Lookup table | `LT` | `LT - Environment by Hostname` |
| 1st party cookie | `COOKIE` | `COOKIE - user_id` |

## Folders

See `folder_structure.md`.

## General rules

1. Separator: ` - ` (space, hyphen, space). Never `_` or `|`.
2. No accents and no special characters in GTM entity names.
3. GA4 event names appear exactly as they are in the dataLayer, in
   `snake_case` - do not localize them in the tag name.
4. Environment at the end, when present: `GA4 - Event - purchase [STG]`.
5. No sequential numbering (`Tag 1`, `Tag 2`) and no author names.

## Approved exceptions

| Entity | Off-standard name | Reason |
| --- | --- | --- |
| | | |
