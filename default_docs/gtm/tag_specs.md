# GTM API - required parameters and error map

Every rule on this page was verified against the live Tag Manager API v2, not
inferred from documentation. The API's error messages are frequently
misleading, and some invalid payloads are accepted silently.

`create_tag` and `create_variable` enforce these rules before sending, and
`get_entity_spec(kind, entity_type)` returns them on demand.

## Required parameters

### Tags

| `type` | Required | Notes |
| --- | --- | --- |
| `googtag` | `tagId` | the destination: `G-`, `AW-` or `GT-` |
| `gaawe` | `eventName` + **exactly one of** `measurementIdOverride` / `measurementId` | see below |
| `gaawc` | `measurementId` | legacy |
| `awct` | `conversionId`, `conversionLabel` | both, always |
| `sp` | `conversionId` | |
| `gclidw` | *(none)* | |
| `flc` | `advertiserId`, `groupTag`, `activityTag`, `ordinalType` | `ordinalType` is easy to miss |
| `fls` | `advertiserId`, `groupTag`, `activityTag`, `revenue`, `orderId` | |
| `html` | `html` | |
| `img` | `url` | |

### Variables

| `type` | Required |
| --- | --- |
| `v` (Data Layer) | `name` |
| `c` (Constant) | `value` |
| `jsm` (Custom JavaScript) | `javascript` |
| `j` (JavaScript Variable) | `name` |
| `k` (1st Party Cookie) | `name` |
| `u`, `smm`, `remm`, `aev`, `d` | *(none — but see the silent-acceptance trap)* |

### Triggers

`customEvent` must have exactly one custom-event filter. The API rejects it
otherwise with `customEventFilter: Custom-event trigger must have exactly one
custom-event filter.` Every other trigger type can be created bare.

---

## The `measurementIdOverride` trap

This is the most confusing error in the API.

```
400 vendorTemplate.parameter.measurementIdOverride: The value must not be empty.
```

The API returns this identical message for **four different mistakes**:

| What you actually did | The real problem |
| --- | --- |
| Omitted both `measurementIdOverride` and `measurementId` | no destination at all |
| Sent `measurementIdOverride: ""` | empty destination |
| Sent `measurementId` as a plain string | wrong parameter type — it must be a `tagReference` |
| Sent `measurementId` naming a tag that does not exist | broken reference |

Note the third and fourth rows: the error names a parameter you never touched.

**The two valid shapes:**

```json
// A. Literal or variable — simplest, use this by default
{"eventName": "purchase", "measurementIdOverride": "{{CONST - GA4 Measurement ID}}"}
```

```json
// B. Reference an existing Google Tag by NAME
{"eventName": "purchase", "measurementId": "Google Tag - GA4"}
```

Shape B requires the parameter to be sent with `type: "tagReference"` rather
than `type: "template"`. A flat JSON string cannot express that, so `create_tag`
applies the conversion automatically for `gaawe.measurementId` and
`gaawc.measurementId`. For any other parameter that needs a non-default type,
use the explicit form:

```json
{"someParam": {"__type__": "tagReference", "value": "Other Tag"}}
```

Never send both `measurementIdOverride` and `measurementId` — they are mutually
exclusive.

---

## Silent acceptance: the errors the API does *not* report

These payloads are accepted with a 200 and produce a tag that looks correct in
the UI while doing nothing or the wrong thing. Only a client-side check catches
them.

| Payload | What happens |
| --- | --- |
| An unknown parameter key (`measurmentIdOverride`, `eventname`) | accepted, ignored at runtime. The setting simply never applies. |
| `flc` with `ordinalType: "bogus"` | accepted. The counting method is undefined at runtime. |
| `googtag` with no firing trigger | accepted. The tag never runs. |
| A lookup table (`smm`) with no `input`/`map` | accepted. Always returns undefined. |

`create_tag` returns these as `warnings` on an otherwise successful create.
A `warnings` array is not noise — read it.

---

## Silent failures the API never reports

Beyond unknown parameter keys, two more things GTM accepts and never mentions:

### A `{{Variable}}` that does not exist

GTM resolves an unknown reference to an **empty string** at runtime. The tag
fires, the UI shows the reference intact, and the value sent is blank. There is
no error anywhere.

```
create_tag(... parameters_json='{"measurementIdOverride": "{{CONST - GA4 Measurement ID}}"}')
-> accepted by the API, sends nothing, looks correct forever
```

`create_tag`, `update_tag`, `create_variable` and `create_trigger` now refuse a
payload whose references the workspace cannot resolve. Two distinct causes, two
different fixes:

| Cause | Fix |
| --- | --- |
| No variable of that name | `create_variable` first, then the tag |
| A GTM **built-in** that is not enabled (`Click Text`, `Form ID`) | enable it in the UI. Creating a user variable with that name would shadow the built-in and behave differently |

Order matters: variables before the tags that use them.

`find_broken_references()` sweeps an existing workspace for the same problem,
grouped by reference — ten tags sharing one missing variable is one finding
with one fix, not ten.

### A tag with no firing trigger

Created successfully, appears in the version diff, never executes.
`create_tag` rejects this for every tag type that exists to run. The escape
hatch is `allow_no_trigger=True`, for a tag fired only by another tag's
sequencing.

---

## Tag-level errors

| Error message | Cause | Fix |
| --- | --- | --- |
| `vendorTemplate.key: Unknown entity type (template public ID: X)` | invalid `tag_type` | see below |
| `enablingTriggerId[0]: Tag references an unknown trigger.` | a trigger id that does not exist | use `list_triggers`, or `list_built_in_triggers` for All Pages / Initialization |
| `Found entity with duplicate name.` | another entity of the same kind has that name | check `list_tags` first; reuse or rename |
| `Invalid value at 'trigger.type' ... "X"` | invalid trigger type | see `gtm/trigger_types.md` |

---

## `Unknown entity type` on a community template

Creating tags from community templates **works through the API**. Verified with
the official Meta, TikTok and Pinterest gallery templates.

The trap is that the tag type has two different shapes:

| Template source | Tag type | Verified |
| --- | --- | --- |
| Community Template Gallery | `cvt_<galleryTemplateId>` | `cvt_MRQN8` → created |
| Hand-written custom template | `cvt_<containerId>_<templateId>` | `cvt_261951688_49` → created |

Applying the wrong shape gives:

```
400 vendorTemplate.key: Unknown entity type (template public ID: cvt_261951688_52)
```

That means the type string does not exist — not that the API refuses
templates. The authoritative value is the `id` field in the template's
`___INFO___` section, which `list_templates` resolves for you.

Always copy `tag_type` verbatim from `list_templates`. Never assemble it by
hand. Then read the parameter contract with `get_template_spec(template_id)`:
templates enforce their own required parameters and their **format** —
Pinterest rejects a `tagId` that does not match `26\d{11}`, Meta rejects a
`pixelId` that is not digits.

Beware the inverse too: some vendor templates validate nothing. The TikTok
Pixel template accepts a tag with no `pixel_code` at all, creating a tag that
looks correct and sends nothing.

See `media/setup_tags.md`.

---

## Rate limiting

```
429 Quota exceeded for quota metric 'Queries' and limit 'Queries per minute'
```

The Tag Manager API allows roughly **0.25 queries per second per user**. A
handful of rapid creates trips it. The client retries automatically with
exponential backoff (4 attempts), so this rarely surfaces — but when creating
many entities in a row, expect the calls to be paced, and do not interpret the
delay as a hang.

---

## Scopes

This project requests `tagmanager.readonly` and `tagmanager.edit.containers`.
It deliberately does **not** request:

- `tagmanager.publish` — the agent never publishes
- `tagmanager.delete.containers` — the agent never deletes

A `403 Insufficient Permission` on a delete or publish call is that decision
working as intended, not a bug.
