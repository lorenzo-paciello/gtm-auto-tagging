# Naming conventions (project standard)

The standard used by `tags_creator_agent` when creating entities and by
`container_organizer_agent` when proposing renames.

> To adopt a different standard, create
> `custom_docs/conventions/naming_conventions.md`. It overrides this file.

## Principle

The name answers three questions without opening the entity: **which tool**,
**what kind of thing it is**, **what it does**.

## Tags

```
<TOOL> - <TYPE> - <DESCRIPTION>
```

| Example | Reads as |
| --- | --- |
| `GA4 - Event - purchase` | GA4 purchase event |
| `GA4 - Event - generate_lead` | GA4 lead event |
| `Google Tag - GA4 + Ads` | the Google base tag |
| `Google Ads - Conversion - Purchase` | purchase conversion |
| `Google Ads - Remarketing - Global` | remarketing |
| `Google Ads - Conversion Linker` | conversion linker |
| `Floodlight - Sales - Purchase` | floodlight sale |
| `Floodlight - Counter - Lead` | floodlight count |
| `Meta - Pixel - Base` | Meta base pixel |
| `Meta - Event - Purchase` | Meta event |
| `Custom HTML - Chat Widget` | third-party script with no template |

Counter-examples (do not use): `ga4 purchase`, `Purchase tag`,
`GA4_Event_Purchase`, `[GA4] purchase`, `Tag 12`, `purchase - john`.

## Triggers

```
<PREFIX> - <CONDITION>
```

| Prefix | Type | Example |
| --- | --- | --- |
| `CE` | custom event | `CE - purchase` |
| `PV` | page view | `PV - Checkout` |
| `DOM` | DOM ready | `DOM - All pages` |
| `WIN` | window loaded | `WIN - Home` |
| `CLK` | click | `CLK - Buy button` |
| `LINK` | link click | `LINK - Outbound` |
| `FORM` | form submission | `FORM - Contact` |
| `VIS` | element visibility | `VIS - Home banner` |
| `SCROLL` | scroll depth | `SCROLL - 75% Blog` |
| `TIMER` | timer | `TIMER - 30s` |
| `HIST` | history change | `HIST - SPA` |
| `INIT` | initialization | `INIT - Consent` |
| `EXC` | exception / blocking | `EXC - Staging` |
| `GRP` | trigger group | `GRP - Consent + Pageview` |

For GA4 events, the event name goes in **exactly as it appears in the
dataLayer**: `CE - add_to_cart`, never `CE - Add to cart`.

Built-in triggers (All Pages, Initialization, Consent Initialization) keep
their reserved names -- do not recreate or rename them.

## Variables

```
<PREFIX> - <SOURCE>
```

| Prefix | Type (`type`) | Example |
| --- | --- | --- |
| `DLV` | `v` - data layer | `DLV - ecommerce.transaction_id` |
| `CONST` | `c` - constant | `CONST - GA4 Measurement ID` |
| `CJS` | `jsm` - custom JavaScript | `CJS - Normalize Email` |
| `JS` | `j` - JavaScript variable | `JS - document.title` |
| `URL` | `u` - URL | `URL - utm_source` |
| `COOKIE` | `k` - 1st party cookie | `COOKIE - user_id` |
| `DOM` | `d` - DOM element | `DOM - Product price` |
| `LT` | `smm` - lookup table | `LT - Environment by Hostname` |
| `RT` | `remm` - regex table | `RT - Page type by URL` |
| `AEV` | `aev` - auto-event variable | `AEV - Click Text` |

For `DLV`, put the real dataLayer path in the name:
`DLV - ecommerce.value` says what the variable reads; `DLV - Value` says
nothing.

## Folders

Short name, no prefix: `GA4`, `Google Ads`, `Floodlight`, `Meta`, `Consent`,
`Utilities`, `Deprecated`. See `conventions/folder_structure.md`.

## General rules

1. Separator ` - ` (space, hyphen, space). Never `_`, `|`, `/` or `::`.
2. No accents and no special characters in entity names.
3. No sequential numbering, no dates, no person names.
4. Environment, when present, goes at the end in brackets:
   `GA4 - Event - purchase [STG]`.
5. Every critical entity has `notes` with the originating requirement, the date
   and the owner.
6. Names are unique within each type. A duplicate name is an audit finding.

## A note on renaming

Renaming a **variable** does not update the `{{Old name}}` references inside
tags and triggers. The orphaned reference starts returning an empty string,
with no visible error. Before renaming any variable: list where it is used,
update the references, and only then rename.

Renaming tags, triggers and folders is safe -- those references are by id.
