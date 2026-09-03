# GTM Auto Tagging

A digital analytics agent that creates, organizes, lists and audits the tagging
of a Google Tag Manager container, guided by a versioned Markdown documentation
set. Built on the [Google ADK](https://google.github.io/adk-docs/), and model
agnostic — Gemini, Claude, GPT, or a local model.

It talks to the GTM API as you, in a **workspace only**: it never publishes and
has no delete tool. Ask it in plain language; it plans, shows you the plan, and
writes after you agree.

```
> Create the GA4 purchase event reading value and currency from the dataLayer

  ✓ check_tagging_prerequisites(ga4)  → Google Tag G-XXXXXXX present
  ✓ preview_tag_conflicts             → nothing equivalent exists
    Plan: 1 trigger (Custom Event: purchase), 1 tag (GA4 - Event - purchase)
    Proceed? y
  ✓ created trigger 41, tag 512
```

```
> Audit my container

  180 tags, 37 accounts initialised across Google, Meta, TikTok,
  Pinterest and LinkedIn.

  [high]   Meta Pixel 156914648903155 initialised twice (tags 258, 500)
  [high]   Meta Pixel 920027463470024 initialised twice (tags 267, 503)
  [medium] 3 Conversion Linkers — keep exactly one
```

## What it will not do

Refusing to add a duplicate is the point of the project, so it is worth being
plain about the limits that come with that:

- **Web containers.** Server-side containers (clients, transformations) are not
  covered.
- **It cannot install a community template.** The API has no method for it; the
  agent tells you which one to add from the gallery and asks for the account id.
- **Template detection is heuristic.** A community template's API type names no
  vendor, so attribution weighs several signals and reports its confidence.
  Treat `uncertain` as "ask", not as "absent".
- **Runtime values are unknowable.** A Custom JavaScript variable or a dataLayer
  value cannot be resolved without running the container, and the agent says so
  rather than guessing.

## Installation

Python 3.10 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### GTM credentials

1. In the Google Cloud Console, enable the **Tag Manager API** and create an
   OAuth 2.0 credential of type *Desktop app*.
2. Download the JSON to `credentials/client_secret.json`.
3. Copy `.env.example` to `.env` and fill in `GTM_ACCOUNT_ID`,
   `GTM_CONTAINER_ID` and `GTM_WORKSPACE_ID`.

The ids are in the GTM URL:

```
tagmanager.google.com/#/container/accounts/<ACCOUNT_ID>/containers/<CONTAINER_ID>/workspaces/<WORKSPACE_ID>
```

On the first API call, a browser opens for OAuth consent and the token is
cached in `credentials/token.pickle`.

### Model provider

Set three variables in `.env`. No code changes are needed to switch providers.

```bash
# Google AI Studio (default, free tier available)
GTM_MODEL_PROVIDER=google
GOOGLE_API_KEY=...
GTM_MODEL_FAST=gemini-3.1-flash-lite
GTM_MODEL_REASONING=gemini-3.1-flash-lite
```

```bash
# Anthropic  (pip install anthropic)
GTM_MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
GTM_MODEL_FAST=claude-haiku-4-5
GTM_MODEL_REASONING=claude-opus-5
```

```bash
# OpenAI / Azure / Ollama / Bedrock  (pip install litellm)
GTM_MODEL_PROVIDER=litellm
OPENAI_API_KEY=sk-...
GTM_MODEL_FAST=openai/gpt-4o-mini
GTM_MODEL_REASONING=openai/gpt-4o
```

See **[docs/model_providers.md](docs/model_providers.md)** for every provider,
pricing, per-role guidance, and what a model must support to run this project.

## Usage

```powershell
adk web             # chat UI in the browser
adk run gtm_agent   # terminal
```

Example requests:

- "What's in my container today?" → `tags_listing_agent`
- "Create the purchase event reading from the dataLayer" → `tags_creator_agent`
- "Organize everything into folders by tool" → `container_organizer_agent`
- "Audit my container" → `auditor_agent`
- "I want to document my ecommerce events" → `default-docs-builder` skill

## Architecture

```
                      ┌──────────────────────┐
                      │   gtm_auto_tagger    │  root agent: routes work and
                      │  (+ project skills)  │  answers conceptual questions
                      └──────────┬───────────┘
              ┌──────────────────┼──────────────────┬──────────────────┐
              ▼                  ▼                  ▼                  ▼
   tags_creator_agent  container_organizer  tags_listing_agent   auditor_agent
     creates tags,       _agent               inventories          diagnoses
     triggers,           folders +            (read-only)          (read-only)
     variables           naming
              └──────────────────┴──────────────────┴──────────────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   ▼                                   ▼
            tools/ (GTM API v2)              default_docs/ + custom_docs/
```

### Sub agents

| Agent | Writes? | Responsibility |
| --- | --- | --- |
| `tags_creator_agent` | yes | creates and adjusts tags, triggers and variables per the standard documentation |
| `container_organizer_agent` | yes | creates folders, moves entities, standardizes naming |
| `tags_listing_agent` | no | inventories and container queries |
| `auditor_agent` | no | audit with severities, event coverage and an action plan |

The root agent decides who to transfer to. For compound requests ("audit it,
then organize it") it chains the specialists in the right order.

### Standard documentation

`default_docs/` is the source of truth every agent consults before acting: GA4
events (automatic, recommended, ecommerce), platform limits, Google Ads,
Floodlight, the GTM API types, the container dependency chain, and the naming,
folder and audit conventions.

`custom_docs/` holds the user's own documentation and **takes precedence**: a
file with the same relative path overrides the default. The
`default-docs-builder` skill walks the user through creating those files.

## Setup tag checks

Every measurement platform works the same way: a setup (base) tag loads the
library, and event tags assume it is already there. An event tag on a missing
setup tag fails silently — the tag exists, the workspace looks healthy, Preview
reports it as fired, and no data is collected.

`check_tagging_prerequisites(product=...)` runs before any write:

| Creating | Requires | If missing |
| --- | --- | --- |
| GA4 Event (`gaawe`) | Google Tag with a `G-` destination, or `gaawc` | **blocking** |
| Google Ads Conversion / Remarketing | Conversion Linker (`gclidw`) | **blocking** |
| Google Ads Conversion / Remarketing | Google Tag with an `AW-` destination | **high** |
| Floodlight (`flc` / `fls`) | Conversion Linker (`gclidw`) | **blocking** |
| Floodlight via Google Tag | Google Tag with a `DC-` destination | recommended |
| A third-party media event tag (35 platforms) | that platform's base pixel — *if* it has one | **blocking** / **high** |
| Any advertising tag | Consent Initialization trigger | recommended |

**Destination, not just presence.** A Google Tag's destination is the prefix of
its `tagId` — `G-` (GA4), `AW-` (Google Ads), `DC-` (Floodlight). One pointing
at GA4 does nothing for Google Ads, and a container that has one is routinely
assumed to cover both. The check reads the prefix and names the mismatch:

```
google_ads  base_google_tag  status=missing  severity=high
  1 Google Tag(s) exist but none targets AW-:
  Google Tag - GA4 -> G-1234567890.
```

A `GT-` container id routes to destinations configured outside GTM, so the
container cannot tell what it covers — that returns `status: "uncertain"`
rather than a guess in either direction.

Third-party severity is computed from the template itself: one that declares
`inject_script` and reaches a vendor host loads the pixel library on its own,
so a missing base tag costs page-view coverage (**high**) rather than all data
(**blocking**). Verified: Meta and Pinterest self-bootstrap, TikTok does not.

Setup-vs-event is read from the template's own parameters too, because nothing
connects the vendors' naming — Meta `eventName`, TikTok `event`, Reddit
`eventType`, Snapchat `eventName`, and Criteo's loader declares no event at
all. A template with parameters but no event parameter is a loader; a tag
setting its event to a page-view value is the base tag; anything else is an
event tag; and when nothing is set, the tag is reported `unclassified` rather
than guessed.

When it returns `ready: false`, the missing setup tag goes into the same plan
and is created first. It also warns about duplicate base tags — two `googtag`
tags on the same destination double-count every page view.

**Third-party pixels** have no stable API type, so detection weighs signals by
strength: **strong** (the tag's type maps to an installed gallery template, or
its Custom HTML carries the vendor snippet) or **weak** (a platform-specific
parameter, the tag name). Attribution needs one strong signal or two weak ones.

Parameter names shared between platforms count for nothing on their own —
`tagId` belongs to Pinterest, to Microsoft UET *and* to Google's `googtag`, and
treating it as evidence once made a container with one Google Tag report
duplicate base pixels for two platforms that were not there. Native Google tag
types are excluded from media matching outright. See
[media/setup_tags.md](default_docs/media/setup_tags.md).

It also exposes the reserved built-in trigger ids (`2147479553` All Pages,
`2147479573` Initialization, `2147479572` Consent Initialization), which
`list_triggers` does not return.

## Community templates

Creating tags from community templates **works through the API** — verified by
creating real purchase tags on the official Meta, TikTok and Pinterest gallery
templates.

The trap is that the tag type has two shapes:

| Template source | Tag type | Example |
| --- | --- | --- |
| Community Template Gallery | `cvt_<galleryTemplateId>` | `cvt_MRQN8` |
| Hand-written custom template | `cvt_<containerId>_<templateId>` | `cvt_261951688_49` |

Applying the wrong one returns `400 Unknown entity type`, which reads like the
API refusing templates and is really a type string that does not exist. The
authoritative value is the `id` declared in the template's own `___INFO___`
block; `list_templates` resolves it.

```python
list_templates()                  # copy `tag_type` verbatim — never rebuild it
get_template_spec(template_id)    # read the parameter contract
create_tag(tag_type=..., parameters_json=...)
```

Step 2 is not optional. Parameter names are vendor-specific — Meta `pixelId`,
TikTok snake_case `pixel_code`, Pinterest `tagId` — and templates validate
**format** as well as presence:

| | Meta Pixel | TikTok Pixel | Pinterest Pixel Tag |
| --- | --- | --- | --- |
| `tag_type` | `cvt_5RM3Q` | `cvt_MRQN8` | `cvt_NGMPN` |
| Account id | `pixelId` | `pixel_code` | `tagId` |
| Format | `^[0-9,]+$` | *(unvalidated)* | `26\d{11}` |
| Purchase event | `eventName`=`Purchase` | `event`=`CompletePayment` | `eventName`=`checkout` |

`get_template_spec` extracts required flags, regex patterns, string lengths and
numeric constraints from the template's `valueValidators`, and `create_tag`
checks them before sending — so a placeholder id fails locally with the
expected format rather than as an opaque 400. Values written as `{{Variable}}`
skip format checking, since they resolve at runtime.

Beware the inverse: an empty `required_parameters` is a trap, not a green
light. The TikTok template validates nothing, so a tag with no `pixel_code` is
accepted and sends nothing — `create_tag` emits a warning in that case.

**This is generic, not a lookup table for three vendors.** The spec comes from
whatever the template declares, so a Klaviyo, Taboola or in-house template
behaves identically. The parser covers `TEXT`, `CHECKBOX`, `SELECT`
(`selectItems`), `RADIO` (`radioItems` — a different key), `GROUP` (flattened,
since the subParams are the real API keys), `LABEL` (skipped as help text),
`PARAM_TABLE`/`SIMPLE_TABLE` columns, `valueValidators`, `enablingConditions`,
and the vendor's own `help` / `valueHint` text — verified lossless across all
64 parameters of the three official templates.

The one part that *is* a fixed registry is platform detection in
`media_platforms.py` (35 platforms, by gallery owner, initialisation snippet
and parameter names),
which powers the "does a setup tag already exist" check. A template outside
that list still works for tag creation; it just does not get the automatic
prerequisite check. Adding one is a single registry entry.

The one thing the API genuinely cannot do is **install** a gallery template. If
one is missing, the agent says which to install rather than silently falling
back to Custom HTML — a template tag carries consent settings, validation and
readable configuration that a script blob does not.

## Payload validation

The GTM API rejects incomplete payloads with messages that often name the wrong
parameter, and it *accepts* unknown parameter keys silently — so a typo
produces a tag that looks correct in the UI and does nothing.

Every rule in [gtm/tag_specs.md](default_docs/gtm/tag_specs.md) was verified
against the live API. `create_tag` and `create_variable` check the payload
before sending; `get_entity_spec(kind, type)` returns the spec on demand.

The worst offender, and the reason this layer exists:

```
400 vendorTemplate.parameter.measurementIdOverride: The value must not be empty.
```

The API returns that identical message for four different mistakes — including
two where `measurementIdOverride` was never passed at all. A GA4 Event tag
needs `eventName` plus **exactly one** of:

```json
{"eventName": "purchase", "measurementIdOverride": "{{CONST - GA4 Measurement ID}}"}
{"eventName": "purchase", "measurementId": "Google Tag - GA4"}
```

The second form must be sent as a `tagReference` rather than a template string,
which flat JSON cannot express — `create_tag` applies that conversion
automatically.

## Safety

The project is designed not to damage a production container:

| Guarantee | How |
| --- | --- |
| Never publishes | the `tagmanager.publish` scope is never requested |
| Never deletes | there is no delete tool |
| Draft only | every write lands in the workspace |
| Confirmation before writing | the prompts require a user-approved plan |
| Never writes a duplicate | `create_tag` and `update_tag` compare the payload with the whole container first and refuse; only the user can override |
| Simulation mode | `GTM_DRY_RUN=true` returns the payload without calling the API |
| Safe concurrent writes | updates use `fingerprint` (optimistic locking) |

Publishing stays a manual user action in the GTM UI, after testing in Preview.

## Structure

```
gtm-auto-tagging/
├── .env                     # secrets (not committed)
├── .env.example
├── requirements.txt
├── credentials/             # client_secret.json + token.pickle (not committed)
├── docs/
│   ├── model_providers.md   # provider guide: Gemini, Claude, GPT, local
│   └── usage_and_testing.md # quota metrics + two-workspace test plan
├── default_docs/            # the project's standard documentation
│   ├── ga4/                 # automatic, recommended, ecommerce events, limits
│   ├── google_ads/          # conversions, remarketing, enhanced conversions
│   ├── floodlight/          # counter, sales, uN variables
│   ├── media/               # third-party pixels and their setup tags
│   ├── gtm/                 # prerequisites, tag specs + error map, API types
│   └── conventions/         # naming, folders, audit checklist
├── custom_docs/             # user documentation (overrides default)
├── tests/                   # run each with: .venv\Scripts\python.exe tests\<file>
│   ├── test_prompts.py            # instruction-templating invariant
│   ├── test_template_parsing.py   # community-template contract parsing
│   ├── test_media_detection.py    # third-party pixel detection, false positives
│   ├── test_google_destinations.py # G-/AW-/DC-/GT- destination matching
│   ├── test_references.py         # {{Variable}} integrity, firing triggers
│   ├── test_identifiers.py        # destination ids, near-miss references
│   ├── test_tool_registry.py      # no tool registered twice per agent
│   ├── test_tag_identity.py       # duplicates across implementations
│   ├── test_vendor_registry.py    # a real snippet for all 35 platforms
│   └── test_creation_gate.py      # what blocks a write, and what must not
└── gtm_agent/
    ├── agent.py             # root agent
    ├── config.py            # settings from .env
    ├── models.py            # provider resolution (Gemini / Claude / LiteLLM)
    ├── usage.py             # token/request tracking + report CLI
    ├── prompts.py           # root and sub agent instructions (see note below)
    ├── sub_agents/
    │   ├── tags_creator/
    │   ├── container_organizer/
    │   ├── tags_listing/
    │   └── auditor/
    ├── tools/
    │   ├── gtm_client.py       # auth, pagination, retries, error handling
    │   ├── gtm_read.py         # listings, broken references, snapshot
    │   ├── gtm_prerequisites.py # does the container have the foundation?
    │   ├── gtm_write.py        # create/update tags, triggers, variables
    │   ├── gtm_folders.py      # folders and entity movement
    │   ├── gtm_templates.py    # community templates: cvt_ types + param contracts
    │   ├── tag_specs.py        # verified API specs + pre-flight validation
    │   ├── references.py       # {{Variable}} resolution against the workspace
    │   ├── identifiers.py      # what a variable is, and what it could resolve to
    │   ├── gtm_identity_audit.py # check_id_consistency
    │   ├── tag_identity.py     # what a tag configures, and what identifies it
    │   ├── media_platforms.py  # THE registry: 35 platforms + GTM's own types
    │   ├── vendor_snippets.py  # the matching engine over that registry
    │   ├── gtm_duplicates.py   # the audit: what is already duplicated
    │   ├── gtm_creation_gate.py # the pre-write check: would this duplicate?
    │   └── docs_tools.py       # documentation read and write
    └── skills/
        └── default-docs-builder/   # skill for building the user's own docs
```

## Tools available to the agents

**Read** — `list_accounts`, `list_containers`, `list_workspaces`, `list_tags`,
`get_tag`, `list_triggers`, `list_built_in_triggers`, `list_variables`,
`list_built_in_variables`, `list_folders`, `list_templates`,
`get_template_spec`, `check_tagging_prerequisites`, `find_broken_references`,
`check_id_consistency`, `find_duplicate_tags`, `preview_tag_conflicts`,
`get_workspace_status`, `get_container_snapshot`

**Write** — `get_entity_spec`, `create_tag`, `update_tag`, `create_trigger`,
`create_variable`, `rename_entity`

**Organize** — `get_folder_map`, `list_folder_entities`, `create_folder`,
`move_entities_to_folder`

**Documentation** — `list_docs`, `read_doc`, `search_docs`, `save_custom_doc`

Write tools take their configuration as flat JSON (`parameters_json`) and
convert it to the API's `parameter` format automatically — text becomes
`template`, integer becomes `integer`, boolean becomes `boolean`, object
becomes `map`, list becomes `list`.

## A note on prompts and braces

ADK runs a string `LlmAgent.instruction` through session-state substitution on
every call. Its pattern is `{+[^{}]*}+`: it strips the braces and, if what
remains is a valid Python identifier not present in session state, raises
`KeyError: Context variable not found`.

Our instructions are full of GTM's own `{{Variable name}}` syntax and JSON
examples. Most survive by accident — `"error": ...` and
`CONST - GA4 Measurement ID` are not valid identifiers — but a single-word span
like `{{variable}}` is, and it crashes the agent mid-flow.

So every instruction is wrapped in `prompts.static_instruction()`, which makes
ADK skip substitution entirely. If you edit a prompt, do not revert it to a
bare string. [tests/test_prompts.py](tests/test_prompts.py) enforces this:

```powershell
.venv\Scripts\python.exe tests\test_prompts.py
```

## Reference integrity

GTM resolves an unknown `{{Variable}}` to an **empty string** at runtime — the
tag fires, the UI shows the reference intact, and the value sent is blank. A
tag with no firing trigger never executes. The API accepts both silently.

One agent run produced ten GA4 ecommerce tags all pointing at
`{{CONST - GA4 Measurement ID}}`, a variable that was never created, plus two
base tags with no trigger. Nothing reported anything.

Write tools now refuse both, distinguishing the two causes of a broken
reference:

| Cause | Fix given |
| --- | --- |
| No variable of that name | create it first — order matters |
| A GTM built-in that is not enabled | enable it; a user variable with that name would shadow it |

The built-in list comes from the Tag Manager discovery document, not a
remembered table, and display names (`Page URL`) are matched against enum names
(`pageUrl`) by normalization.

`find_broken_references()` sweeps an existing workspace, grouped by reference —
ten tags sharing one missing variable is one finding with one fix. It is part
of the audit checklist and of `get_container_snapshot` insights.

## Identifier consistency

A tag can carry a valid-looking measurement or pixel id that no base tag ever
configures. GTM accepts it, the tag fires, and the data goes to a property
nobody watches. Nothing in the UI compares the two.

`check_id_consistency()` resolves constant variables first, so it compares by
**value** rather than by name:

| Finding | Example | Severity |
| --- | --- | --- |
| `destination_without_base_tag` | a `gaawe` on `G-0987654321` while the Google Tag configures `G-1234567890` | critical |
| `reference_near_miss` | tags on `{{CONST - GA4 Measurement id}}` while `{{CONST - GA4 Measurement ID}}` exists | critical |
| `variable_name_collision` | two variables a human reads as one | high |
| `media_account_id_mismatch` | a platform's tags disagree about the pixel id | critical |
| `destination_not_statically_checkable` | the id comes from a runtime variable | medium |

The near-miss case is the one that costs the most time: GTM matches variable
names byte for byte, so creating the right variable fixes only the tags that
spelled it the same way and leaves the rest silently empty. The fix given is to
repoint the tags, never to create a second variable.

## Duplicate detection

Duplication is a question about **base tags**. On most platforms the account id
appears only in the initialisation call, and event tags use whichever library
that call loaded:

```javascript
fbq('init', '123')            // the account lives here
fbq('track', 'AddToCart')     // no account; uses the pixel above
```

Comparing every tag by account and event name reports noise. On a real 180-tag
container it produced ten groups, seven of them legitimate repeats — twenty GA4
tags firing `click` on twenty pages. Restricting the comparison to
initialisations left three groups, all real.

`find_duplicate_tags()` asks one narrow question — *is this account initialised
more than once?* — across four sections:

| Section | Severity | What it is |
| --- | --- | --- |
| `base` | critical / high | the same account initialised twice; critical when the tags share a trigger or mix implementations |
| `conversion` | critical / medium | identical Google Ads or Floodlight configuration — these carry their own id and label, unlike a GA4 event |
| `script` | high | identical Custom HTML bodies for a vendor no registry names |
| `event_tags_depending_on_a_base_tag` | — | event calls that initialise nothing; not duplicates, but they break if their base tag goes |

It also returns `accounts_initialised`, the container's full pixel inventory —
for most users the first complete list of every account their site loads.

### Coverage beyond the majors

Containers in the wild carry far more than the advertising majors, so there are
two mechanisms:

1. **[media_platforms.py](gtm_agent/tools/media_platforms.py)** — one registry
   of 35 platforms (Meta, TikTok, Pinterest, LinkedIn, Snapchat, Microsoft, X,
   Reddit, Criteo, Taboola, Outbrain, AdRoll, Quora, Amazon, Awin, Rakuten,
   Impact, Adform, RTB House, Teads, Yandex, LINE, Kakao, Naver, VK, Hotjar,
   Clarity, HubSpot, Klaviyo, Intercom, Segment, Mixpanel, Amplitude, Crazy
   Egg, Lucky Orange). Each captures the account id, in script form and in
   image-pixel/noscript URL form, and accepts a `{{Variable}}` where the id
   would be — hand-written pixels are usually parameterised. One entry reaches
   everything: prerequisite checks, media listing, identity audit, duplicates.
2. **Script fingerprint** — two Custom HTML tags whose bodies match, ignoring
   whitespace and `{{Variable}}` references. This covers the vendor nobody
   anticipated. The registry earns its keep by supplying the account id:
   without it, two base tags for *different* accounts of one vendor would look
   identical.

### The gate before the write

Detection is worth nothing if it reports after the fact. Two failures from real
use made that concrete: a Meta base pixel was created for an id already
installed as Custom HTML and the warning arrived *after* the tag existed, and a
GA4 `page_view` event tag was created for a measurement id that already has a
Google Tag with no warning at all.

So `create_tag` and `update_tag` now compare the payload with the whole
container **before** writing, and refuse. (An update excludes the tag being
edited, or every edit would report the tag as a duplicate of itself — but
pointing an existing tag at an account another tag already owns produces the
same duplication by a quieter route, and is blocked.) Nothing is created; the conflict comes back naming the
existing tags. The agent relays it, the user decides, and only then is
`confirm_duplicate=True` passed — a flag that records the user's decision, not
one the agent may set on its own. Four kinds block:

| Kind | Blocks | What it catches |
| --- | --- | --- |
| `initialisation` | yes | the account is already configured — native tag, template, Custom HTML, or a hand-written `gtag('config', …)` |
| `already_sent_by_a_base_tag` | yes | the event is already automatic: a Google Tag sends `page_view` itself, a base pixel fires its own PageView |
| `identical_configuration` | on overlapping triggers | a tag of this type already has this identity |
| `duplicate_conversion` | yes | the same Google Ads conversion or Floodlight activity, native **or** pasted as Custom HTML |
| `possible_duplicate_via_variable` | yes | an existing tag's id is a lookup table that can resolve to this one |
| `identical_script` | yes | the same script, even for a vendor no registry names |
| `duplicate_event_for_account` | on overlapping triggers | this platform already sends this event for this account |

Conversions and base tags (`awct`, `sp`, `flc`, `fls`, `googtag`, `gaawc`,
`gclidw`) block on **any** trigger. Making the identity comparison
trigger-aware was right for a GA4 event placed on a second interaction and
wrong for a conversion action, which the ad platform cannot tell apart from its
twin — a duplicate Google Ads conversion was created live before that
distinction existed.
| `same_identifier` / `missing_prerequisite` / `prefer_template` | no | context, an absent foundation, a template that should be used instead |

`already_sent_by_a_base_tag` is the one no base-tag comparison can find. The
GA4 event tag initialises nothing and the Google Tag is not an event tag, yet
together they count every page view twice in every report in the property.

It also has to read the *right* thing. `send_page_view` is not a top-level
parameter: a Google Tag keeps it in `configSettingsTable` as rows of
`{parameter, parameterValue}`, and a GA4 Configuration in `fieldsToSet` as
`{name, value}`. Reading only the top level told a user their page-view tag
would double-count on a property where they had just turned it off — and the
test meant to cover that case had invented a top-level parameter, so it passed
while the real case failed. `setting_values()` flattens those tables, and every
place that reads a tag's configuration now goes through it or through
`scalar_values()`.

The gate also has to *not* fire. A container holds dozens of GA4 event tags
sharing one measurement id; refusing the next one would make the tool unusable.
A shared identifier is reported as `advisory` and never blocks — and
`eventName: "scroll_75"` is read as an event, not an identifier, because the
parameter name decides. Getting that backwards made two unrelated scroll tags
compare as identical.

The sharpest version of that mistake: identity used to be built from values
that *look* like ids. Floodlight's `groupTag` (`sale`) and `activityTag`
(`purch0`) are short words with no digits, so both were ignored — and every new
activity on an advertiser compared identical to every other one. The check
would have blocked every Floodlight tag a user ever created. `IDENTITY_KEYS`
now states what actually identifies each type, and anything unlisted falls back
to full parameter equality, which cannot over-match.

### GTM's own vendor tag types

Not every third-party tag is a template or a Custom HTML snippet. GTM ships
built-in types for several vendors — LinkedIn Insight is `bzi`, its partner id
in a parameter called simply `id`. They carry no gallery reference and no
vendor snippet, so a survey built on templates and script patterns misses them:
a container's two native LinkedIn tags went unlisted while its two hand-written
ones were found.

`NATIVE_MEDIA_TYPES` names the ones it can, but **that list does not have to be
complete**. `is_unrecognised_vendor_type` catches the rest structurally — not
Google's own type, not `cvt_`, not script — so a vendor type nobody here has
heard of is still read as a base tag, still compared with others of its type,
and still inventoried. The named entry only adds the vendor's label, its setup
guidance, and its place in the prerequisite check.

### Settings that live somewhere else

A tag's configuration sits at three levels, and containers use all three:

1. top-level parameters
2. rows of a nested table (`configSettingsTable`, `fieldsToSet`)
3. rows of a **settings variable** the tag merely references
   (`configSettingsVariable` → a `gtcs` variable)

Level 2 was missed once and told a user their page_view tag would double-count
on a property where they had just turned `send_page_view` off. Level 3 is the
same mistake one indirection further out, and governed containers use it
precisely so twenty tags can share one configuration.

### Coping with vendors nobody registered

The blocking kinds lean on the registry. The advisory one deliberately does
not: `looks_like_an_identifier` recognises an account id by **shape** —
`G-`/`AW-`/`DC-` prefixes, a 5–20 digit run, a `t2_` id, a UUID, or a token
mixing letters and digits — and then searches every existing tag's parameters
for it, expanding `{{Constant}}` references on both sides. So even for a tool
the agent has never heard of, it can still answer *"this id already appears in
tag 327"*. `identical_script` covers the same gap from the other direction.

### Not every platform has a base tag to miss

Each entry declares an `event_model`, because "missing base tag" is not a fault
everywhere:

| Model | Platforms | Missing base tag |
| --- | --- | --- |
| `library` | 27 — Meta, TikTok, Pinterest, Criteo, Taboola, Segment… | **blocking**: event tags call a library the base tag loaded |
| `standalone` | Awin, Rakuten, Impact | not a fault — each tag carries its own account id |
| `single` | Hotjar, Clarity, Crazy Egg, Lucky Orange, Intercom | no event tags depend on it; it just has to fire once, everywhere |

Without that distinction the agent would invent a limitation — telling a user
their Awin sale tag is broken because no Awin "base tag" exists.

### Traps this had to get right

Patterns were originally matched against a `json.dumps` of the parameters,
which escapes `"` as `\"` — every
double-quoted snippet silently stopped matching, hiding all the LinkedIn tags
in a container while Meta kept working because its snippet uses single quotes.
`eventName: "standard"` in Meta's template is a **mode selector**, not the
event. And `eventId` deduplicates a single hit against the Conversions API — it
is unique per fire, so treating it as the account id groups unrelated tags.

A fourth only appeared once the registry grew: several vendors put an
event-shaped call inside their own base snippet. Taboola's base pushes
`name: 'page_view'`, AdRoll's loader calls `__adroll.record_user`, VK's base
ends with `VK.Retargeting.Hit()`, and Criteo's homepage tag pushes `viewHome`
next to `setAccount`. A naive "if it looks like an event, it is not a base tag"
rule made every one of those base tags invisible. Conversely Taboola, Kakao,
Criteo, Naver, AdRoll and VK repeat the account id in *every* call, so matching
an init pattern is not proof of initialisation — `events_repeat_the_id` lets an
event match veto it. [tests/test_vendor_registry.py](tests/test_vendor_registry.py)
runs a realistic snippet for all 35 vendors against both rules.

## Usage and quota

`UsageTrackerPlugin` records one line per model call — agent, model, tokens,
latency — to `usage/model_calls.jsonl`. Read it with:

```powershell
.venv\Scripts\python.exe -m gtm_agent.usage           # every run
.venv\Scripts\python.exe -m gtm_agent.usage --last    # the most recent run
```

The report breaks totals down by agent and by model. The line that matters on a
free tier is `requests per run`: quotas are counted in requests, not tokens, and
every sub agent transfer and tool round trip is its own request.

See [docs/usage_and_testing.md](docs/usage_and_testing.md) for how to read each
number, and for a two-workspace test plan (one empty, one deliberately
neglected) covering every flow.

## Configuration reference

| Variable | Default | Description |
| --- | --- | --- |
| `GTM_MODEL_PROVIDER` | `google` | `google`, `anthropic`, `vertex_anthropic`, `litellm` |
| `GTM_MODEL_FAST` | `gemini-3.1-flash-lite` | model for read-only agents |
| `GTM_MODEL_REASONING` | `gemini-3.1-flash-lite` | model for the root and writing agents |
| `GTM_MODEL_MAX_TOKENS` | `16000` | output cap (Anthropic providers only) |
| `GTM_ACCOUNT_ID` | — | default account |
| `GTM_CONTAINER_ID` | — | default container |
| `GTM_WORKSPACE_ID` | `2` | default workspace |
| `GTM_CLIENT_SECRET_FILE` | `credentials/client_secret.json` | |
| `GTM_TOKEN_FILE` | `credentials/token.pickle` | |
| `GTM_DEFAULT_DOCS_DIR` | `default_docs` | |
| `GTM_CUSTOM_DOCS_DIR` | `custom_docs` | |
| `GTM_SKILLS_DIR` | `gtm_agent/skills` | |
| `GTM_DRY_RUN` | `false` | `true` simulates writes |

## Contributing

The two things most likely to need extending, and how:

**A media platform.** One entry in
[gtm_agent/tools/media_platforms.py](gtm_agent/tools/media_platforms.py): the
label, its `event_model`, the gallery markers, and regexes for the
initialisation call capturing the account id as group 1. Then add a realistic
snippet to `SNIPPETS` in
[tests/test_vendor_registry.py](tests/test_vendor_registry.py), which checks
that the base snippet is recognised, that **no other** platform matches it, and
that the event snippet is not read as an initialisation.

**Documentation.** `default_docs/` is plain Markdown, read by the agents at run
time. Editing it changes behaviour without touching code.

Run the tests before opening a pull request — they need no network and no
credentials:

```powershell
Get-ChildItem tests\*.py | ForEach-Object { .venv\Scripts\python.exe $_.FullName }
```

```bash
for f in tests/*.py; do ./.venv/bin/python "$f"; done
```

## Roadmap

- Server-side container support (`serverPageview`, clients, transformations)
- A versioning sub agent (`create_version`, diffing between versions)
- Inventory export to spreadsheet or BigQuery
- dataLayer validation via Preview/Debug before creating the tag

## License

MIT — see [LICENSE](LICENSE).
