# GTM - tag types in the API v2

The `type` field in a tag body uses a short code that differs from the name
shown in the UI. Use this table when calling `create_tag` and when translating
an inventory back for the user.

## Google

| `type` | UI name | Main parameters |
| --- | --- | --- |
| `googtag` | Google Tag | `tagId` (G-XXXX, AW-XXXX or GT-XXXX), `configSettingsTable`, `eventSettingsTable` |
| `gaawe` | Google Analytics: GA4 Event | `eventName`, `measurementId` or `measurementIdOverride`, `eventSettingsTable`, `userProperties`, `sendEcommerceData`, `getEcommerceDataFrom` |
| `gaawc` | Google Analytics: GA4 Configuration (legacy, replaced by `googtag`) | `measurementId`, `fieldsToSet` |
| `awct` | Google Ads Conversion Tracking | `conversionId`, `conversionLabel`, `orderId`, `conversionValue`, `currencyCode`, `enableProductReporting`, `enableEnhancedConversion` |
| `sp` | Google Ads Remarketing | `conversionId`, `customParams`, `enableDynamicRemarketing` |
| `gclidw` | Conversion Linker | `enableCrossDomain`, `acceptIncoming`, `linkerDomains`, `cookiePrefix` |
| `flc` | Floodlight Counter | `advertiserId`, `groupTag`, `activityTag`, `countingMethod`, `ordinalValue`, `enableGoogleAttributionOptions` |
| `fls` | Floodlight Sales | `advertiserId`, `groupTag`, `activityTag`, `orderId`, `revenue`, `quantity` |
| `gaawllm` | Google Analytics: user-provided data | `userDataSource`, email/phone/address fields |
| `ua` | Universal Analytics (sunset) | critical audit finding: it no longer collects data |

## Generic

| `type` | UI name | Use |
| --- | --- | --- |
| `html` | Custom HTML | `html`, `supportDocumentWrite`. Last resort |
| `img` | Custom Image Pixel | `url`, `cacheBusterQueryParam`, `useCacheBuster` |
| `cvt_<galleryTemplateId>` | Community template from the gallery | parameters defined by the template; get the exact type from `list_templates` |
| `cvt_<containerId>_<templateId>` | Hand-written custom template | idem |
| `zone` | Zone (360 containers) | |

## Common third parties

Meta, LinkedIn, TikTok and similar pixels almost always appear as gallery
templates (`cvt_*`) or as `html`. When inventorying, identify them by tag name
and parameter contents, not by `type`.

## Building `parameters_json`

`create_tag` takes a flat JSON string and converts it to the API's `parameter`
format. Conversion rules:

| Python/JSON value | API type |
| --- | --- |
| text | `template` |
| integer | `integer` |
| `true` / `false` | `boolean` |
| object `{}` | `map` |
| list `[]` | `list` |

References to GTM variables use `{{Variable name}}` inside the text.

### Example - base Google Tag

```json
{"tagId": "{{CONST - GA4 Measurement ID}}"}
```

Fire it on `2147479573` (Initialization - All Pages) or `2147479553` (All
Pages). See `gtm/prerequisites.md`.

### Example - GA4 event with parameters

```json
{
  "eventName": "generate_lead",
  "measurementIdOverride": "{{CONST - GA4 Measurement ID}}",
  "eventSettingsTable": [
    {"parameter": "form_name", "parameterValue": "{{DLV - form_name}}"},
    {"parameter": "value", "parameterValue": "{{DLV - lead_value}}"},
    {"parameter": "currency", "parameterValue": "USD"}
  ]
}
```

### Example - ecommerce reading the dataLayer

```json
{
  "eventName": "purchase",
  "measurementIdOverride": "{{CONST - GA4 Measurement ID}}",
  "sendEcommerceData": true,
  "getEcommerceDataFrom": "dataLayer"
}
```

### Example - Google Ads conversion

```json
{
  "conversionId": "{{CONST - Google Ads Conversion ID}}",
  "conversionLabel": "AbC-D_efG-h12_34-567",
  "orderId": "{{DLV - ecommerce.transaction_id}}",
  "conversionValue": "{{DLV - ecommerce.value}}",
  "currencyCode": "USD"
}
```

### Example - Floodlight Sales

```json
{
  "advertiserId": "1234567",
  "groupTag": "purchase",
  "activityTag": "trans0",
  "orderId": "{{DLV - ecommerce.transaction_id}}",
  "revenue": "{{DLV - ecommerce.value}}",
  "countingMethod": "TRANSACTIONS"
}
```

## Project rules

1. `html` only when no native tag and no gallery template exists. Every `html`
   tag needs a justification in `notes`.
2. Measurement and conversion ids live in constant variables, never typed into
   the tag -- otherwise switching environments becomes a manual hunt.
3. Every advertising tag declares `consentSettings`.
4. Configure Consent Initialization and Conversion Linker before any conversion
   tag. See `gtm/prerequisites.md`.
