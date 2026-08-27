# GTM - the container dependency chain

The single most expensive mistake in Tag Manager is creating an event tag on
top of a foundation that does not exist. The tag is created, the workspace
looks healthy, the change appears in the version diff -- and no data is
collected. Nothing errors.

`check_tagging_prerequisites(product=...)` automates the checks on this page.
Run it before creating any tag listed in the "Depends on" column below.

## The chain

```
1. Consent Initialization  (CMP / Consent Mode defaults)
        ↓
2. Conversion Linker       (gclidw)  ── stores gclid/wbraid in a 1st-party cookie
        ↓
3. Base tag                (googtag) ── the measurement destination: G-, AW-, GT-
        ↓
4. Event / conversion tags (gaawe, awct, sp, flc, fls)
```

| You are creating | Depends on | Severity if missing |
| --- | --- | --- |
| GA4 Event (`gaawe`) | Google Tag with a `G-` destination, or legacy `gaawc` | **blocking** |
| Google Ads Conversion (`awct`) / Remarketing (`sp`) | Conversion Linker (`gclidw`) | **blocking** |
| Google Ads Conversion / Remarketing | Google Tag with an `AW-` destination | **high** |
| Floodlight Counter / Sales (`flc` / `fls`) | Conversion Linker (`gclidw`) | **blocking** |
| Floodlight through the Google Tag | Google Tag with a `DC-` destination | recommended |
| Meta / TikTok / Pinterest / LinkedIn / Snapchat / X / Reddit / Microsoft Ads / Criteo event tag | that platform's base pixel tag | **blocking** or **high**, depending on whether the template loads the library itself |
| Any advertising tag | Consent Initialization trigger | recommended |

The destination matters as much as the presence -- see the next section.

Third-party pixels follow exactly the same pattern as Google — a setup tag
loads the library, event tags assume it is there. See
`media/setup_tags.md` for the per-platform reference and why detecting them is
heuristic.

## A Google Tag is not "a" Google Tag

The destination lives in the prefix of the tag's `tagId`, and a tag pointing at
one destination does **nothing** for another:

| Prefix | Destination | Satisfies |
| --- | --- | --- |
| `G-` | Google Analytics 4 | GA4 event tags |
| `AW-` | Google Ads | enhanced conversions, remarketing |
| `DC-` | Floodlight / Campaign Manager 360 | Floodlight through the Google Tag |
| `GT-` | Google Tag container | **unknown** — see below |

This is the most common false sense of security in a container: one Google Tag
exists, everyone assumes measurement is set up, and Google Ads has been running
without an `AW-` destination the whole time. `check_tagging_prerequisites`
checks the prefix, not just the presence, and reports the mismatch explicitly:

```
google_ads  base_google_tag  status=missing  severity=high
  1 Google Tag(s) exist but none targets AW-:
  Google Tag - GA4 -> G-1234567890.
  A Google Tag for one destination does nothing for another.
```

### `GT-` is genuinely undecidable from the container

A `GT-` id is a Google Tag *container* whose destinations are configured in the
Google Tag interface, not in GTM. Reading the container tells you nothing about
what it routes to. The check reports `status: "uncertain"` and asks the user —
it must not be counted as coverage, and must not be reported as missing either.

### Is a missing destination fatal?

Not usually, and the severity says so:

| Product | Requirement | Severity | Why |
| --- | --- | --- | --- |
| GA4 | Google Tag `G-`/`GT-` | **blocking** | a `gaawe` tag has no measurement context of its own |
| Google Ads | Conversion Linker | **blocking** | without it the conversion is not attributed |
| Google Ads | Google Tag `AW-`/`GT-` | **high** | an `awct` tag still records the conversion, but enhanced conversions, remarketing audiences and cross-device attribution need the `AW-` destination |
| Floodlight | Conversion Linker | **blocking** | attribution under third-party cookie restrictions |
| Floodlight | Google Tag `DC-`/`GT-` | recommended | optional when dedicated `flc`/`fls` tags are in place |

## Why the base tag matters even when gtag.js is already on the page

A common objection: *"the site loads gtag.js directly, so the GA4 event tag
works without a Google Tag in the container."* Often true in practice, and
still wrong as a setup:

- **Nobody can audit it.** Reading the container tells you nothing about which
  property receives the data, which consent defaults apply, or which fields are
  set on the config.
- **Nobody can change it.** Switching measurement id, adding a server-side
  endpoint, or setting `user_id` becomes a developer ticket instead of a
  container change.
- **Versioning breaks.** A container version rollback does not roll back a
  hardcoded on-page snippet.
- **Ordering is unguaranteed.** The container has no way to make sure the
  snippet initialized before the event tag fires.

If the client genuinely wants the base tag to stay outside the container,
record that decision in the `notes` of the first event tag, naming the
measurement id and where the snippet lives.

## Duplicate base tags

Two `googtag` tags pointing at the same destination double-count every page
view -- inflating sessions, halving engagement rate, and corrupting every
conversion rate downstream. This is a **critical** audit finding, not a
cosmetic one.

`check_tagging_prerequisites` reports it in `warnings`. It is easy to create
accidentally: GTM's own onboarding wizard offers to add a Google Tag, and a
second one arrives with an imported container or a template.

## Reserved built-in triggers

GTM keeps three triggers outside the workspace trigger collection.
`list_triggers` does not return them and `triggers().get()` answers 404 for
them, but their ids are valid `firingTriggerId` values:

| Trigger id | Name | Type | Use for |
| --- | --- | --- | --- |
| `2147479553` | All Pages | `pageview` | standard page view firing |
| `2147479572` | Consent Initialization - All Pages | `consentInit` | the CMP, before everything |
| `2147479573` | Initialization - All Pages | `init` | consent-aware base tags |

Use `list_built_in_triggers()` to retrieve them. **Never create a new
"All Pages" trigger** -- an extra `pageview` trigger next to the built-in one
is a classic source of duplicate firing.

## Firing order inside the container

GTM evaluates in this order regardless of how you name your tags:

1. `consentInit` triggers
2. `init` triggers
3. `pageview` triggers
4. `domReady`, `windowLoaded`
5. everything else, as its trigger conditions are met

Use tag sequencing (`setupTag` / `teardownTag`) only when this order is not
enough. Sequencing is invisible in the tag list and hard to audit, so document
it in `notes` whenever you use it.

## Checklist before creating an event tag

- [ ] `check_tagging_prerequisites` returns `ready: true`
- [ ] Exactly one setup tag per destination / pixel account
- [ ] The setup tag has a firing trigger (a `googtag` with none never runs)
- [ ] The setup tag is not paused
- [ ] The measurement / conversion / pixel id comes from a constant variable
- [ ] A Consent Initialization trigger exists if advertising tags are involved
- [ ] For a third-party pixel: the community template is installed, and
      `list_templates` gives you the `cvt_` type to use as `tag_type`
