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

35 platforms are recognised, grouped by how their event tags relate to their
base tag. That grouping is what decides whether a missing base tag is a fault
at all: reporting one for an Awin sale tag would be a limitation the agent
invented. `check_tagging_prerequisites` returns the group as `event_model`.

### `library` -- 27 platforms

Event tags call a library the base tag loaded. **A missing base tag is blocking.**

| Platform | `product` key | Account id format |
| --- | --- | --- |
| Meta (Facebook) Pixel | `meta` | 15-16 digit numeric pixel id |
| TikTok Pixel | `tiktok` | 20-character alphanumeric pixel code (e.g. C4A1B2C3D4E5F6G7H8I9) |
| Pinterest Tag | `pinterest` | 13-digit numeric tag id |
| LinkedIn Insight Tag | `linkedin` | 6-8 digit numeric partner id |
| Snap Pixel | `snapchat` | UUID-style pixel id |
| Microsoft Advertising UET | `microsoft_ads` | 8-9 digit numeric UET tag id |
| X (Twitter) Pixel | `x_twitter` | alphanumeric pixel id (e.g. o1a2b) |
| Reddit Pixel | `reddit` | advertiser id starting with t2_ |
| Criteo OneTag | `criteo` | 5-6 digit numeric account id |
| Taboola Pixel | `taboola` | numeric account id |
| Outbrain Pixel | `outbrain` | alphanumeric marketer id |
| AdRoll | `adroll` | 22-character advertiser id |
| Quora Pixel | `quora` | 32-character hexadecimal pixel id |
| Amazon Ads | `amazon_ads` | UUID-style tag id |
| Adform | `adform` | numeric client id |
| RTB House | `rtb_house` | advertiser hash |
| Teads | `teads` | numeric analytics tag id |
| Yandex Metrica | `yandex_metrica` | 8-9 digit numeric counter id |
| LINE Tag | `line` | hyphenated alphanumeric tag id |
| Kakao Pixel | `kakao` | 13-digit numeric track id |
| Naver Common Tag | `naver` | account id starting with s_ |
| VK Pixel | `vk` | pixel id starting with VK-RTRG- |
| HubSpot | `hubspot` | numeric portal (hub) id |
| Klaviyo | `klaviyo` | 6-character public API key (company id) |
| Segment | `segment` | write key |
| Mixpanel | `mixpanel` | 32-character hexadecimal project token |
| Amplitude | `amplitude` | 32-character hexadecimal API key |

### `standalone` -- 3 platforms

Each tag carries its own account id. Nothing has to run first, so nothing can be missing.

| Platform | `product` key | Account id format |
| --- | --- | --- |
| Awin | `awin` | numeric advertiser id |
| Rakuten Advertising | `rakuten` | numeric merchant id |
| Impact | `impact` | Universal Tracking Tag id (starts with A) |

### `single` -- 5 platforms

One install tag, no event tags depending on it. It just has to fire on every page, once.

| Platform | `product` key | Account id format |
| --- | --- | --- |
| Hotjar | `hotjar` | numeric site id |
| Microsoft Clarity | `clarity` | 10-character project id |
| Crazy Egg | `crazy_egg` | 8-digit account number, split across the script path |
| Lucky Orange | `lucky_orange` | alphanumeric site id |
| Intercom | `intercom` | 8-character app id |

Parameter names are deliberately absent from this table. They come from
`get_template_spec`, never from documentation: a template author can rename
anything, and several already have -- TikTok's official template uses
snake_case `pixel_code`, Snapchat's uses `accountId` where every guess says
`pixelId`, and Criteo's loader declares no event parameter at all.

Adding a platform is one entry in `gtm_agent/tools/media_platforms.py`. That
single entry reaches everything: the prerequisite check before a tag is
created, the media listing, the identity audit and duplicate detection. There
used to be two registries -- a short one for prerequisites and a longer one for
duplicates -- and they drifted, so a container could be told its Taboola pixel
was installed twice while the creator agent had never heard of Taboola.

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

### Before creating anything: the duplication gate

`create_tag` compares the payload with the whole container before it writes,
and **refuses** if it would duplicate something. Nothing is created. The
conflict names the existing tags, and the decision is the user's:

1. relay what already exists -- name and id, so they can look at it
2. say what you would add and why
3. ask
4. only if they agree, call again with `confirm_duplicate=true`, and record
   their reason in the tag `notes`

Renaming the tag does not get past it: the comparison is by configuration.

Seven kinds block. Four are about identity -- `initialisation`,
`identical_configuration`, `duplicate_conversion`, `identical_script` -- and
they compare **across implementations**: a native `awct` and a hand-written
`gtag('event','conversion',{send_to:'AW-…/label'})` are the same conversion, an
`flc` tag and a pasted Floodlight iframe counter are the same activity, and a
`googtag` and a hand-written `gtag('config','G-…')` configure the same
property. A half-finished migration is exactly where these hide from each
other.

`already_sent_by_a_base_tag` is the one that is easy to miss: a Google Tag
sends `page_view` on its own, and a base pixel fires its own PageView when it
loads, so a separate page-view event tag for the same account counts every page
view twice.

`possible_duplicate_via_variable` exists because a variable is not always one
value. A container that routes GA4 by lookup table -- 27 URL patterns to 27
measurement ids behind one Google Tag -- already covers all 27 properties, and
a check that resolves only Constants would call a 28th tag for one of them
clean.

`duplicate_event_for_account` and, for GA4 events and media tags,
`identical_configuration` block only when the triggers overlap. On different
triggers they ask instead: a second placement of the same measurement on a
separate interaction is ordinary work. **Conversions never get that leniency** --
the same Google Ads id and label, or the same Floodlight advertiser/group/
activity, is one conversion action counted twice however it is triggered.

### GTM's own vendor tag types

Not every third-party tag is a community template or a Custom HTML snippet.
GTM ships built-in types for several vendors -- LinkedIn Insight is `bzi`, with
its partner id in a parameter simply called `id`. They carry no gallery
reference and no vendor snippet, so a survey built only on templates and script
patterns misses them completely, and a container's native LinkedIn tags can go
unlisted while its hand-written ones are found. Both the prerequisite check and
the duplication gate read them through `NATIVE_MEDIA_TYPES`; adding a vendor
type is one entry -- but the list does not have to be complete. A built-in
type nobody named is still recognised structurally (not Google's own, not a
template, not script), so it is still read as a base tag and still compared.
Naming it adds the label, the setup guidance and the prerequisite check.

### Where a setting actually lives

Three levels, and containers use all three: the tag's own parameters, the rows
of a nested table (`configSettingsTable`, `fieldsToSet`), and the rows of a
**settings variable** the tag only references (`configSettingsVariable`). When
you inspect a tag yourself, follow all three before concluding a setting is
absent -- a value you cannot see is not a value that is not there.

A duplicate is not always a mistake. Two base tags with mutually exclusive
triggers -- different domains, different environments -- are legitimate, and so
is a `page_view` event tag when the base tag has `send_page_view` disabled.
That is exactly why the flag exists and why only the user may set it.

The check reads that switch from where GTM actually keeps it. `send_page_view`
is **not** a top-level parameter: a Google Tag holds it in
`configSettingsTable` as `{parameter, parameterValue}` rows, and a legacy GA4
Configuration in `fieldsToSet` as `{name, value}`. The same is true of much
else -- an account id can sit in a settings row as readily as in a top-level
field. When you inspect a tag yourself, look inside its tables before
concluding a setting is absent; a value you cannot see is not a value that is
not there.

For a plan with several tags, run `preview_tag_conflicts` on each first, so
everything that already exists is presented in one message rather than
discovered after two tags were written.

### Duplication is a question about base tags only

Most platforms carry the account id in exactly one place -- the initialisation
call -- and their event tags use whichever library that call loaded:

```javascript
fbq('init', '123')            // the account lives here
fbq('track', 'AddToCart')     // no account; uses the pixel above
```

So comparing every tag by account and event name reports noise rather than
findings. On a real 180-tag container it produced ten groups, seven of which
were legitimate repeats: twenty GA4 tags firing `click` on twenty pages, seven
Meta `Lead` tags on seven campaigns. Restricting the comparison to
initialisations left three groups, all real.

`find_duplicate_tags()` therefore asks one narrow question -- **is this account
initialised more than once?** -- and reports event tags separately, since an
event tag cannot duplicate a base tag.

The one exception is a conversion tag. A Google Ads conversion carries its own
id and label, unlike a GA4 event, so two identical ones on the same trigger
double-count. On different triggers it is usually deliberate.

### A pixel written by hand is still that pixel

A vendor pixel installed as Custom HTML or as a Custom Image URL is invisible
to any check that reads tag types. That is how a container ends up with the
same pixel twice -- once from the gallery template, once as a script -- with
nothing reporting it. In one real 180-tag container, 19 of the pixels were
hand-written.

`find_duplicate_tags()` recognises every registered platform in three written
forms:

| Form | Example |
| --- | --- |
| Init call | `fbq('init','123')`, `ttq.load('X')`, `_linkedin_partner_id = "5919468"` |
| Per-call id | `fbq('trackSingleCustom','123','Click')`, `ttq.instance('X').track(...)` |
| Image pixel / noscript | `facebook.com/tr?id=123&ev=PageView`, `ct.pinterest.com/v3/?tid=...`, `bat.bing.com/action/0?ti=...` |

Two rules keep this honest:

- **Match the raw parameter value, never a JSON dump.** `json.dumps` escapes
  `"` as `\"`, so a double-quoted snippet stops matching. This once hid every
  LinkedIn tag in a container while Meta kept working, purely because Meta's
  snippet uses single quotes.
- **A vendor domain is not always the ad product.** Microsoft Clarity is
  heatmaps, not UET, and must not be reported as an ad account.

Some snippets genuinely carry no account id:

```javascript
fbq('track', 'AddToCart', {...})   // uses the last-initialised pixel
ttq.track('Registration')          // uses the loaded instance
```

There is nothing to extract, and guessing from the tag name would be an
invention. These are reported under `unattributed_vendor_tags` -- they cannot
be compared for duplication, and they break outright if the base pixel they
depend on is ever removed.

### What is checked always, and what is registry-bound

Two different mechanisms, and it is worth keeping them apart:

| | Trigger | Scope |
| --- | --- | --- |
| **Parameter validation** (`get_template_spec`, `create_tag`) | the tag type starts with `cvt_` | **every** template, any vendor |
| **Setup-tag prerequisite** (`check_tagging_prerequisites`) | the platform is in `media_platforms.py` | the 35 listed platforms |

So a CMP, an A/B testing tool or an in-house template gets full parameter
validation -- required fields, allowed values, regex, unknown-key warnings --
even though no prerequisite check exists for it. Verified against a consent
platform template outside the registry: nine required parameters caught, the
enum rejected, the typo flagged.

The reverse is the gap: nothing tells the agent that an unregistered vendor
needs a base tag before its event tags. Adding one is a single registry entry.

**What is not generic** is the platform registry in `media_platforms.py`, which
powers `check_tagging_prerequisites`: it knows 35 platforms by gallery owner,
initialisation snippet and parameter names. A template outside that list can
still have tags created from it; what will not happen automatically is the
"does a setup tag already exist for this platform" check. Adding a platform is
one entry in the registry.

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
