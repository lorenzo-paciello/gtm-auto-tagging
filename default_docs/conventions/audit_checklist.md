# GTM container audit checklist

The list `auditor_agent` walks through. Each item gets **OK / Fix / N/A**, with
evidence (entity name and id).

> To adopt a different checklist, create
> `custom_docs/conventions/audit_checklist.md`.

## 1. Foundation and load order

- [ ] Exactly one Google base tag (`googtag` or `gaawc`) per destination
- [ ] No duplicate base tags pointing at the same measurement id
- [ ] Every base tag has a firing trigger and is not paused
- [ ] Consent Initialization fires before any other tag
- [ ] Conversion Linker (`gclidw`) present and firing on all pages
- [ ] No advertising tag fires before consent is known
- [ ] No Universal Analytics (`ua`) tags still active
- [ ] No event tag whose product foundation is missing (`check_tagging_prerequisites`)

## 2. GA4

- [ ] Measurement ID comes from a constant variable, not typed into the tag
- [ ] No `gaawe` tag duplicating an enhanced measurement event
      (`page_view`, `scroll`, `click`, `file_download`, `form_start`,
      `form_submit`, `video_*`, `view_search_results`)
- [ ] Event names in `snake_case`, up to 40 characters, no reserved prefix
- [ ] Events use Google's recommended name where an equivalent exists
- [ ] No event carries a segmentation in its name (`purchase_mobile`)
- [ ] Ecommerce events read the `ecommerce` object from the dataLayer
- [ ] `purchase` has `transaction_id`, `value` and `currency`
- [ ] Custom parameters are registered as custom dimensions/metrics in GA4
- [ ] No text value exceeds 100 characters

## 3. Paid media

- [ ] `conversionId` / `conversionLabel` come from variables
- [ ] Purchase conversions carry `orderId` (deduplication)
- [ ] `currencyCode` present whenever a value is sent
- [ ] No double counting: an `awct` tag alongside a GA4-imported conversion
- [ ] Floodlight `fls` has `orderId` filled
- [ ] `groupTag` / `activityTag` documented in `notes`
- [ ] Floodlight `uN` custom variables documented

## 4. Consent and privacy

- [ ] `consentSettings` declared on advertising tags
- [ ] The consent mode in use (basic or advanced) is identified and documented
- [ ] No plain personal data (email, phone, national id) in a variable or tag
- [ ] Enhanced Conversions use the native `user_data` field or SHA-256 hashing
- [ ] No third-party tag collecting data not declared in the privacy policy

## 5. Triggers

- [ ] No tag with an empty `firingTriggerId`
- [ ] Triggers reused across media, with no per-tool clones
- [ ] No duplicate "All Pages" trigger next to the built-in one
- [ ] `purchase` does not fire more than once per order (refresh, SPA)
- [ ] Staging environment blocking configured
- [ ] The built-in variables the active triggers need are enabled

## 6. Variables, references and identifiers

- [ ] Data Layer Variables use `dataLayerVersion: 2`
- [ ] Measurement and conversion ids live in constants
- [ ] `jsm` variables have `notes` explaining what they do
- [ ] No duplicate variable names
- [ ] `find_broken_references()` returns `clean: true`
- [ ] `check_id_consistency()` returns `clean: true`

These two tools cover four failures that are invisible in the GTM UI:

| Failure | What actually happens |
| --- | --- |
| `{{Name}}` pointing at nothing | resolves to an empty string; the tag fires and sends blank |
| Tag with no firing trigger | never executes |
| A destination id no base tag configures | the tag fires and the data goes to a property nobody watches |
| Two variables differing only in case | fixing one leaves the tags on the other still empty |

The third is the one an eyeball audit never finds: `G-0987654321` is a
perfectly valid measurement id, and nothing compares it against the `G-` the
container's Google Tag actually configures. `check_id_consistency` resolves
constant variables first, so it compares by value rather than by name.

## 7. Organization

- [ ] Every entity is in a folder
- [ ] Names follow `conventions/naming_conventions.md`
- [ ] No duplicate names within a type
- [ ] `notes` filled on the critical entities
- [ ] No near-duplicate folder names (`GA4` and `GA 4`)

## 8. Hygiene

- [ ] No orphan triggers (no tag references them)
- [ ] No apparently unused variables (verify the `jsm` ones by hand)
- [ ] Paused tags have a justification and a deadline
- [ ] No `html` doing what a native tag or template already does
- [ ] The workspace has no pending merge conflicts

## 9. Coverage

- [ ] Every critical event from the documentation is implemented
- [ ] Each implemented event carries its required parameters
- [ ] Media conversions cover the same business events as GA4
- [ ] Error and form-failure events exist (the funnel nobody measures)

## Severity

| Level | Criterion |
| --- | --- |
| **Critical** | data lost, duplicated or sent wrong; legal risk |
| **High** | compliance or maintenance risk that has not broken yet |
| **Medium** | organization, readability, documentation |
| **Low** | cleanup and hygiene |

## Report format

1. Executive summary (3 to 5 lines) + a justified 0-10 score
2. Container numbers per product
3. Table: severity | entity (id) | problem | recommendation
4. Event coverage: implemented vs missing
5. Prioritized action plan, naming the sub agent responsible for each item
