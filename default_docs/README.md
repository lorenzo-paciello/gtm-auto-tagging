# Standard tagging documentation

The source of truth the project's agents follow when they create, organize and
audit a GTM container. Based on Google's public documentation for GA4, Google
Ads, Floodlight/CM360 and the Tag Manager API v2.

> These documents describe the **generic** standard. To override any file here
> with the reality of your own business, create a file with the **same relative
> path** inside `custom_docs/`. The `default-docs-builder` skill walks you
> through that.

## Map

| Path | Contents |
| --- | --- |
| `ga4/events_automatically_collected.md` | automatic and enhanced measurement events |
| `ga4/events_recommended.md` | Google's recommended events, by vertical |
| `ga4/events_ecommerce.md` | the full ecommerce funnel and the `items` array |
| `ga4/limits_and_naming_rules.md` | platform limits, reserved names, naming rules |
| `google_ads/conversion_tracking.md` | conversions, remarketing, conversion linker, enhanced conversions |
| `floodlight/floodlight.md` | counter, sales, `u=` custom variables, cache buster |
| `media/setup_tags.md` | third-party pixels (Meta, TikTok, Pinterest, LinkedIn...) and their base tags |
| `gtm/prerequisites.md` | the container dependency chain: what must exist before what |
| `gtm/tag_specs.md` | required parameters per type and the API error map, verified against the live API |
| `gtm/tag_types.md` | each tag's `type` in the API v2 and its main parameters |
| `gtm/trigger_types.md` | each trigger's `type` and how to build filters |
| `gtm/variable_types.md` | each variable's `type` and its parameters |
| `conventions/naming_conventions.md` | naming standard for tags, triggers, variables and folders |
| `conventions/folder_structure.md` | the folder organization criterion |
| `conventions/audit_checklist.md` | the checklist used by `auditor_agent` |

## Precedence

1. `custom_docs/<path>` - the user's documentation (always wins)
2. `default_docs/<path>` - this set
3. The model's general knowledge - last resort, and it must be flagged as such

## Maintenance

Google's specifications change. When this text and the real behaviour of the
API or the UI disagree, the API wins. Record the correction in `custom_docs/`
rather than editing this directory, so a project update does not overwrite it.
