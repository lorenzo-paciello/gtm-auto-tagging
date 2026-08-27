# Floodlight (Campaign Manager 360 / Display & Video 360)

Floodlight measures conversions from Google Marketing Platform display and
video campaigns. The configuration lives in CM360; GTM only fires the tag.

## Tag types

| `type` | Name | Use |
| --- | --- | --- |
| `flc` | Floodlight Counter | counts actions: page views, leads, visits to a section |
| `fls` | Floodlight Sales | counts transactions with revenue and quantity |

## Parameters

### Counter (`flc`)

| Parameter | Description |
| --- | --- |
| `advertiserId` | the CM360 advertiser id (`src=`) |
| `groupTag` | Group Tag String (`cat=` at group level, e.g. `lead`) |
| `activityTag` | Activity Tag String (`type=`, e.g. `contact0`) |
| `countingMethod` | `STANDARD` (every time), `UNIQUE` (once per user/day), `PER_SESSION` |
| `ordinalValue` | the `ord=` value. A random number for standard, `1` for unique |
| `enableGoogleAttributionOptions` | enables `attributionOptionImage` |
| `customVariable` | the `u1`..`u100` variable table |

### Sales (`fls`)

| Parameter | Description |
| --- | --- |
| `advertiserId` | advertiser id |
| `groupTag` / `activityTag` | same as counter |
| `orderId` | the order id - **deduplication**, goes into `ord=` |
| `revenue` | transaction revenue |
| `quantity` | number of items |
| `countingMethod` | `TRANSACTIONS` (one row per order) or `ITEMS_SOLD` |
| `customVariable` | `u1`..`u100` |

## Custom variables (`u1`..`u100`)

These are Floodlight's extra parameters, mapped in CM360. What each `uN` means
is defined **in the CM360 account**, not in GTM.

```json
{
  "advertiserId": "1234567",
  "groupTag": "purchase",
  "activityTag": "trans0",
  "orderId": "{{DLV - ecommerce.transaction_id}}",
  "revenue": "{{DLV - ecommerce.value}}",
  "quantity": "{{DLV - ecommerce.total_items}}",
  "countingMethod": "TRANSACTIONS",
  "customVariable": [
    {"key": "u1", "value": "{{DLV - customer_type}}"},
    {"key": "u2", "value": "{{DLV - payment_type}}"}
  ]
}
```

Always ask the user for the CM360 **custom variable map** before filling in
`uN`. Sending data into the wrong `u` pollutes the advertiser's reporting and
is hard to detect afterwards.

## Cache buster (`ord=`)

| Counting method | `ord` value |
| --- | --- |
| Standard / Unique (counter) | a random number - the GTM tag generates it |
| Per session (counter) | the session id |
| Sales | `orderId` - guarantees deduplication |

On `fls`, an empty `orderId` makes CM360 count every refresh as a new sale.
Critical audit finding.

## Container prerequisites

1. **Conversion Linker** (`gclidw`) on all pages - Floodlight depends on it for
   attribution in browsers that restrict third-party cookies.
2. **Consent Mode** with `ad_storage` and `ad_user_data`.
3. If the site uses a first-party measurement domain, configure it in the tag
   options.

See `gtm/prerequisites.md`.

## Naming

`Floodlight - Counter - <action>` and `Floodlight - Sales - <action>`, with the
`groupTag`/`activityTag` recorded in the tag `notes`. Without that, nobody can
map a GTM tag back to a CM360 activity.

## Audit checklist

- [ ] `advertiserId` correct and consistent across tags
- [ ] `groupTag` and `activityTag` match the CM360 activities
- [ ] `fls` has `orderId` filled
- [ ] `countingMethod` matches what the activity expects
- [ ] Conversion Linker present
- [ ] `consentSettings` declared
- [ ] `uN` variables documented in `notes`
- [ ] No duplicate Floodlight for the same activity
