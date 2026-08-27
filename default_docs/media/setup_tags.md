# Third-party media - setup (base) tags

Google is not special. Meta, TikTok, Pinterest, LinkedIn and every other pixel
follow the same two-layer pattern:

```
1. Setup tag   -- loads the platform's JS library, registers the account id
        ↓
2. Event tags  -- call functions that only exist because layer 1 ran
```

A `Purchase` event tag for TikTok with no `ttq.load()` before it does not
error. The function reference fails silently, the tag reports as fired in
Preview, and the platform receives nothing.

**Always run `check_tagging_prerequisites(product="<platform>")` before
creating a third-party event tag.**

## Platform reference

| Platform | `product` key | Account id parameter | Base snippet marker | Event call |
| --- | --- | --- | --- | --- |
| Meta (Facebook) Pixel | `meta` | `pixelId` | `fbq('init', ...)` | `fbq('track', ...)` |
| TikTok Pixel | `tiktok` | `pixel_code` | `ttq.load(...)`, `ttq.page()` | `ttq.track(...)` |
| Pinterest Tag | `pinterest` | `tagId` | `pintrk('load', ...)` | `pintrk('track', ...)` |
| LinkedIn Insight Tag | `linkedin` | `partnerId` | `_linkedin_partner_id` | `lintrk('track', ...)` |
| Snap Pixel | `snapchat` | `accountId` * | `snaptr('init', ...)` | `snaptr('track', ...)` |
| Microsoft Advertising UET | `microsoft_ads` | `tagId` | `uetq`, `bat.bing.com/bat.js` | `uetq.push('event', ...)` |
| X (Twitter) Pixel | `x_twitter` | `pixelId` | `twq('config', ...)` | `twq('event', ...)` |
| Reddit Pixel | `reddit` | `id` * | `rdt('init', ...)` | `rdt('track', ...)` |
| Criteo Loader | `criteo` | `partnerId` * | `static.criteo.net/js/ld/ld.js` | `criteo_q.push(...)` |

\* Verified against the installed template. The column is a convenience only:
the parameter names come from `get_template_spec`, never from this table --
a template author can rename anything, and several already have.

Account id formats:

| Platform | Format |
| --- | --- |
| Meta | 15-16 digit numeric |
| TikTok | 20-character alphanumeric pixel code |
| Pinterest | 13-digit numeric |
| LinkedIn | 6-8 digit numeric partner id |
| Snapchat | UUID-style |
| Microsoft Ads | 8-9 digit numeric UET tag id |
| Reddit | advertiser id starting with `t2_` |

## Why detection is heuristic

Google tags have stable API types (`gaawe`, `awct`). Third-party pixels do not:
they arrive as community templates whose type is `cvt_<galleryTemplateId>`,
which says nothing about the vendor unless you look up the template.

Detection therefore weighs signals by strength:

**Strong** — one is enough:

1. The tag's type maps to an installed gallery template whose owner or
   repository names the platform (`facebook`, `tiktok`, `pinterest`).
2. Its Custom HTML contains the vendor's own snippet (`fbq('init'`,
   `pintrk('load'`, `ttq.load(`).

**Weak** — two are needed:

3. A parameter name claimed by exactly one platform and by no native Google
   tag (`pixel_code`, `partnerId`, `uetTagId`).
4. The tag name.

Parameter names shared between platforms — `tagId`, `pixelId`, `advertiserId`
— count for nothing on their own. `tagId` alone belongs to Pinterest, to
Microsoft UET and to Google's `googtag`, and treating it as evidence is exactly
what produced phantom duplicate pixels. Native Google tag types are excluded
from media matching outright; only `html` and `img` stay in scope.

`check_tagging_prerequisites` reports which signals matched and a `confidence`:

- `confidence: "high"` — a strong signal matched. Treat as found.
- `confidence: "medium"` — two weak signals. Plausible; verify before acting.
- `status: "uncertain"` — the tag could not be placed. **Ask the user.** Never
  create a second base pixel on a guess; a duplicate double-counts every event.

## Creating template-backed tags through the API

**This works.** Verified against the live API with the official Meta, TikTok
and Pinterest gallery templates — all three purchase tags created successfully.

### The tag type depends on where the template came from

| Template source | Tag type | Example |
| --- | --- | --- |
| Community Template Gallery | `cvt_<galleryTemplateId>` | `cvt_MRQN8` |
| Hand-written custom template | `cvt_<containerId>_<templateId>` | `cvt_261951688_49` |

Every template declares its own public id in the `___INFO___` block of its
`templateData`, and that value is authoritative:

```
Pinterest   galleryTemplateId=NGMPN   ___INFO___.id = "cvt_NGMPN"
Meta        galleryTemplateId=5RM3Q   ___INFO___.id = "cvt_5RM3Q"
TikTok      galleryTemplateId=MRQN8   ___INFO___.id = "cvt_MRQN8"
```

Applying the custom-template shape to a gallery template returns:

```
400 vendorTemplate.key: Unknown entity type (template public ID: cvt_261951688_52)
```

That means **the type string does not exist**, not that the API refuses
community templates. `list_templates` resolves the correct value — copy its
`tag_type` field verbatim and never assemble it from parts.

### The three-step workflow

```
list_templates()                 -> copy `tag_type` verbatim
get_template_spec(template_id)   -> read the parameter contract
create_tag(tag_type=..., parameters_json=...)
```

### Real parameters for the big three

Read from the installed templates, not from memory:

| | Meta Pixel | TikTok Pixel | Pinterest Pixel Tag |
| --- | --- | --- | --- |
| `tag_type` | `cvt_5RM3Q` | `cvt_MRQN8` | `cvt_NGMPN` |
| Gallery owner | `facebook` | `tiktok` | `pinterest` |
| Account id param | `pixelId` | `pixel_code` | `tagId` |
| Id format | `^[0-9,]+$` | *(unvalidated)* | `26\d{11}` |
| Purchase event | `eventName` = `Purchase` | `event` = `CompletePayment` | `eventName` = `checkout` |
| Also required | `advancedMatchingList` | *(nothing)* | `adeEventName` (`^[a-zA-Z_]+$`) |
| Property table | `objectPropertyList` (name/value) | flat params: `value`, `currency`, `order_id` | flat params: `value`, `currency`, `order_id` |

Note the casing trap: TikTok uses snake_case `pixel_code`, Meta uses camelCase
`pixelId`. Guessing gets you a silently ignored parameter.

### Templates validate format, not just presence

`get_template_spec` extracts three kinds of constraint from the template's
`valueValidators`, and `create_tag` checks them before sending:

| Validator | Example | Effect |
| --- | --- | --- |
| `NON_EMPTY` | Meta `pixelId` | required |
| `REGEX` | Pinterest `tagId` → `26\d{11}` | format enforced |
| `STRING_LENGTH` | Pinterest `currency` → exactly 3 | length enforced |
| `NUMBER` | Pinterest `order_quantity` | numeric |

So a placeholder id fails before it reaches the API:

```
Invalid Pixel ID format
  fix: The Meta Pixel template requires `pixelId` to match `^[0-9,]+$`.
       Ask the user for the real value rather than a placeholder.
```

Values written as `{{Variable}}` skip format checking — they resolve at
runtime, so only literals can be validated up front.

### Any template works, including ones nobody anticipated

Tag creation is **generic**. Nothing about it is specific to Meta, TikTok or
Pinterest: `get_template_spec` reads whatever the template declares in its own
`___TEMPLATE_PARAMETERS___` block. A Klaviyo, Taboola or in-house template
behaves identically.

What the parser handles, verified against the real vendor templates (64
parameters across the three, none lost):

| Declaration | Handling |
| --- | --- |
| `TEXT`, `CHECKBOX` | emitted as-is |
| `SELECT` | options from `selectItems` |
| `RADIO` | options from `radioItems` — a different key, easy to miss |
| `GROUP` | flattened; the `subParams` are the real API keys, the group is not |
| `LABEL` | skipped — help text, not a parameter |
| `PARAM_TABLE`, `SIMPLE_TABLE` | column names listed |
| `valueValidators` | required / regex / length / numeric constraints |
| `enablingConditions` | reported as "only applies when ..." |
| `help`, `valueHint`, `checkboxText` | the vendor's own explanation, passed through |

That last row is what lets an agent configure a template it has never seen. The
TikTok template, read cold, describes itself:

```
pixel_code  [TEXT]
    label: Pixel ID
    help:  You can find your Pixel ID in Events Manager
    hint:  CD9079RC77U0N3GBV16Y
email       [TEXT]
    only when: ['hash equals non-hashed']
```

### What is checked always, and what is registry-bound

Two different mechanisms, and it is worth keeping them apart:

| | Trigger | Scope |
| --- | --- | --- |
| **Parameter validation** (`get_template_spec`, `create_tag`) | the tag type starts with `cvt_` | **every** template, any vendor |
| **Setup-tag prerequisite** (`check_tagging_prerequisites`) | the platform is in `media_platforms.py` | the nine listed advertising platforms |

So a CMP, an A/B testing tool or an in-house template gets full parameter
validation -- required fields, allowed values, regex, unknown-key warnings --
even though no prerequisite check exists for it. Verified against a consent
platform template outside the registry: nine required parameters caught, the
enum rejected, the typo flagged.

The reverse is the gap: nothing tells the agent that an unregistered vendor
needs a base tag before its event tags. Adding one is a single registry entry.

**What is not generic** is the platform registry in `media_platforms.py`, which
powers `check_tagging_prerequisites`: it knows nine platforms by gallery owner
and parameter names. A template outside that list can still have tags created
from it; what will not happen automatically is the "does a setup tag already
exist for this platform" check. Adding a platform is one entry in the registry.

### Does a missing setup tag actually break anything?

It depends on the template, and the answer is readable from the template
itself. A template that declares the `inject_script` permission and reaches a
vendor host loads the pixel library on its own; one that only reads and calls
window globals needs something else to have loaded it first.

Verified against the three official templates:

| Template | Loads the library? | Evidence | Missing setup tag |
| --- | --- | --- | --- |
| Meta Pixel | yes | `inject_script` + `connect.facebook.net/en_US/fbevents.js` + `fbq('init', pixelId)` | **high** |
| Pinterest Pixel Tag | yes | `inject_script` + `s.pinimg.com/ct/core.js` + `pintrk('load', tagId)` | **high** |
| TikTok Pixel | **no** | no `inject_script` permission, no vendor URL, only `callInWindow` into an existing `ttq` | **blocking** |

- **blocking** -- the event tag calls a function that does not exist. Nothing
  is sent, and nothing errors visibly.
- **high** -- the event tags do send data, but the pixel only initializes on
  pages where an event fires. Page views, audience building and view-through
  attribution are all incomplete.

`check_tagging_prerequisites` computes this per platform and reports it as
`template_self_bootstraps`. Do not describe a `high` finding as "no data is
being collected" -- that is false and the user will discover it.

### False positives this detection used to produce

Three faults once combined to report "duplicate base setup tags detected for
Pinterest and Microsoft Advertising" in a container with one Pinterest tag and
no Microsoft tag at all. Understanding them is useful when judging any
detection result:

1. **Shared parameter names.** `tagId` belongs to Pinterest, to Microsoft UET
   and to Google's own `googtag`. A parameter name is treated as evidence only
   when exactly one platform claims it and no native Google tag uses it --
   `tagId`, `pixelId` and `advertiserId` are therefore worth nothing on their
   own.
2. **Native types in scope.** A `googtag`, `gaawe`, `awct`, `flc` or `gclidw`
   is never a third-party pixel and is now excluded outright. Only `html` and
   `img` stay in scope, since they legitimately host vendor snippets.
3. **Events read as setup tags.** A tag setting an event parameter to anything
   other than a page view is an event tag. When neither an event nor a base
   signal is present, the tag is reported as `unclassified` rather than assumed
   to be a base tag.

Attribution now needs one **strong** signal (the tag's type maps to an
installed gallery template, or its Custom HTML contains the vendor snippet) or
two **weak** ones (a platform-specific parameter, the tag name).

### Setup vs event is read from the template, not from a vendor list

Hardcoding per-vendor parameter names does not survive contact with reality:

| Template | Event parameter | Account id parameter |
| --- | --- | --- |
| Meta Pixel | `eventName` | `pixelId` |
| TikTok Pixel | `event` | `pixel_code` |
| Pinterest Pixel Tag | `eventName` **and** `adeEventName` | `tagId` |
| Snapchat | `eventName` | `accountId` |
| Reddit Pixel | `eventType` | `id` |
| Criteo Loader | *(none)* | `partnerId` |

No pattern connects those. So the role is derived from the template's own
parameter declarations instead:

1. The template declares **no** event parameter at all → it is a loader, and
   every tag built on it is a setup tag. This is what identifies Criteo's.
2. The tag sets an event parameter to a page-view value → setup tag.
3. The tag sets it to anything else → event tag.
4. Nothing set, no base keyword in the name → `unclassified`. Not guessed.

A template whose parameters could not be parsed declares nothing, which is not
the same as declaring no events — rule 1 does not apply to it.

### Consent Initialization is checked by tag, not by trigger

Consent Initialization is a **reserved** trigger (`2147479572`). It never
appears in `list_triggers`, so looking for a trigger whose type is
`consentInit` reports "missing" in every container, correctly configured ones
included. The check looks for a **tag firing on the reserved id**.

A CMP fired on All Pages (`2147479553`) instead runs too late: measurement tags
may already have fired before the default consent state is set. That is
reported as missing, with the reason.

### An empty `required_parameters` is a trap, not a green light

The TikTok Pixel template marks **nothing** as required. A TikTok tag with no
`pixel_code` at all is accepted by the API, appears correct in the UI, and
sends nothing. `create_tag` emits a warning in this case. Always confirm the
account id is set regardless of what the template claims to validate.

### What the API genuinely cannot do

Install a template. There is no endpoint for adding a Community Template
Gallery template to a container. When one is missing, stop and tell the user:

1. which template to install (Templates → Search Gallery → the official one
   from the platform's own repository);
2. that you need the account id.

### Custom HTML is the fallback, not the default

A Custom HTML base tag with the platform's snippet, fired on
Initialization - All Pages, does work. But compared to the official template it
loses:

- **Consent Mode integration** — the template declares `consentSettings`;
  Custom HTML must be gated with a blocking trigger instead.
- **Validation** — the template rejects a missing pixel id; Custom HTML accepts
  any string.
- **Readability** — a reviewer sees named fields rather than a script blob.
- **Maintenance** — the vendor updates the template; your snippet goes stale.

Use it when the user does not want to install a template, and say what they are
giving up.

## Firing order

Base pixels go on **Initialization - All Pages** (`2147479573`), the same as
the Google Tag, so they load before any event trigger can fire. Do not use All
Pages (`2147479553`) for a base pixel in a container that has consent
management — Initialization runs after Consent Initialization, which is what
you want.

## Consent

Third-party advertising pixels need `consentSettings` declared just like Google
Ads tags — typically `ad_storage` and `ad_user_data`. A community template that
supports Consent Mode exposes this; a Custom HTML implementation does not, and
must be blocked by a trigger exception instead. Flag Custom HTML pixels without
consent handling as a **high** severity audit finding.

## Audit checklist

- [ ] Every platform with event tags also has exactly one active setup tag
- [ ] Each setup tag has a firing trigger and is not paused
- [ ] No duplicate base pixel for the same account id
- [ ] Setup tags fire on Initialization, before their event tags
- [ ] Account ids come from constant variables, not literals
- [ ] `consentSettings` declared, or a blocking trigger in place
- [ ] Official gallery templates preferred over Custom HTML
- [ ] The account id in the container matches the one in the ad platform UI
