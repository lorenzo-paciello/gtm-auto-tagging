# Google Ads - conversions, remarketing and enhanced conversions

## Required components

| Order | Tag | `type` | Role |
| --- | --- | --- | --- |
| 1 | Consent Initialization (CMP) | `html` or template | sets the consent state before anything else |
| 2 | Conversion Linker | `gclidw` | stores `gclid`/`wbraid` in a first-party cookie (`_gcl_*`). **Without it the conversion is not attributed** |
| 3 | Google Tag (AW-XXXX) or conversion tag | `googtag` / `awct` | sends the conversion |
| 4 | Remarketing | `sp` | audiences and dynamic remarketing |

The Conversion Linker must fire on **all pages**, using the
`Initialization - All Pages` trigger (`2147479573`).

## Conversion tag (`awct`)

| Parameter | Required | Description |
| --- | --- | --- |
| `conversionId` | yes | the digits only from `AW-XXXXXXXXX` |
| `conversionLabel` | yes | the conversion action label |
| `conversionValue` | recommended | monetary value. Use a dataLayer variable |
| `currencyCode` | if a value is sent | ISO 4217 (`USD`) |
| `orderId` | recommended | the order id; this is what **deduplicates** conversions |
| `enableProductReporting` | ecommerce | enables `merchantId`, `itemsByDataLayer` |
| `enableEnhancedConversion` | recommended | turns on enhanced conversions |
| `userDataVariable` | with EC | a user-provided data variable |

`conversionId` and `conversionLabel` always come from constant variables, never
typed into the tag.

## Deduplication

Without `orderId`, a refresh on the thank-you page counts the conversion again.
In an audit, any `awct` purchase tag without `orderId` is a **critical**
finding.

## Enhanced conversions

Send hashed user data to improve attribution.

- **Never** build the hash by hand in Custom JavaScript unless you have to: the
  Google tag performs the SHA-256 and the normalization for you.
- Accepted fields: `email`, `phone_number`, `address` (`first_name`,
  `last_name`, `street`, `city`, `region`, `postal_code`, `country`).
- Phone numbers in E.164 format (`+15551234567`).
- Email lowercased and trimmed.
- Requires accepting the customer data terms in Google Ads.
- Requires a legal basis for the processing. Record that in the client's
  documentation.

Recommended implementation: the "Google Analytics: user-provided data" tag
(`gaawllm`) or the `userDataVariable` field inside `awct` itself.

## Remarketing (`sp`)

For dynamic remarketing, the custom parameters must match the business type
configured in Google Ads:

| Vertical | Parameters |
| --- | --- |
| Retail | `ecomm_prodid`, `ecomm_pagetype`, `ecomm_totalvalue` |
| Education | `dynx_itemid`, `dynx_pagetype`, `dynx_totalvalue` |
| Travel | `dynx_itemid`, `dynx_itemid2`, `dynx_pagetype`, `dynx_totalvalue` |

`ecomm_pagetype` values: `home`, `searchresults`, `category`, `product`,
`cart`, `purchase`, `other`.

## Importing GA4 conversions instead of using `awct`

A valid alternative: mark the event as a key event in GA4 and import it into
Google Ads. Upsides: a single implementation, GA4's attribution model.
Downsides: more latency and a dependency on the account link.

**Never run both for the same conversion** -- Google Ads counts it twice. In an
audit, check whether an `awct` purchase tag coexists with a GA4-imported
conversion.

## Consent Mode

Google Ads tags should declare `consentSettings`:

```json
{
  "consentStatus": "NEEDED",
  "consentType": {"type": "list", "list": ["ad_storage", "ad_user_data", "ad_personalization"]}
}
```

With advanced Consent Mode, tags fire even without consent, sending cookieless
pings (conversion modeling). With basic mode, they do not fire at all. That
choice belongs to the client's legal team -- document which one is in use.

## Audit checklist

- [ ] Conversion Linker present and firing on all pages
- [ ] Conversion Linker fires BEFORE the conversion tags
- [ ] `conversionId` and `conversionLabel` come from variables
- [ ] `orderId` filled on purchase conversions
- [ ] `currencyCode` present whenever `conversionValue` is set
- [ ] No double counting (`awct` plus a GA4-imported conversion)
- [ ] `consentSettings` declared
- [ ] No plain personal data being sent
