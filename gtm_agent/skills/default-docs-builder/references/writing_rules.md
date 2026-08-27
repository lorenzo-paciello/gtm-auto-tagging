# Quality rules for tagging documentation

Standard documentation serves three readers: the analyst who implements it, the
developer who has to populate the dataLayer, and the agent that automates it.
If any of the three cannot act on the text, the document has failed.

## 1. Write a contract, not a tutorial

Wrong: "The purchase event should be sent when the user makes a purchase."

Right:

> `purchase` — fires on the order confirmation page (`/checkout/success`), from
> the `purchase` dataLayer event pushed by the back end after payment is
> confirmed. It must never fire on the gateway return before confirmation.

## 2. One parameter table per event

| Parameter | Type | Required | Source | Example |
| --- | --- | --- | --- | --- |
| `transaction_id` | string | yes | `dataLayer.ecommerce.transaction_id` | `ORD-100294` |
| `value` | number | yes | `dataLayer.ecommerce.value` | `459.90` |
| `currency` | string | yes | constant | `USD` |

Without the "Source" column the developer does not know what to deliver, and
the agent does not know which variable to create.

## 3. Document the dataLayer alongside the event

Include the exact expected snippet:

```javascript
dataLayer.push({ ecommerce: null });
dataLayer.push({
  event: "purchase",
  ecommerce: {
    transaction_id: "ORD-100294",
    value: 459.90,
    currency: "USD",
    items: [{ item_id: "SKU-1", item_name: "Basic tee", price: 89.90, quantity: 1 }]
  }
});
```

Pushing `ecommerce: null` before each ecommerce event stops values from the
previous event leaking into the next one.

## 4. Naming rules need counter-examples

A rule without a counter-example gets interpreted three different ways by three
different people. Always pair the rule with both:

- Right: `GA4 - Event - purchase`
- Wrong: `ga4 purchase`, `Purchase tag GA4`, `GA4_Event_Purchase`

## 5. Record the foundation each product needs

State which base tag has to exist before the events you are documenting:

| Event group | Foundation |
| --- | --- |
| GA4 events | Google Tag with `G-XXXXXXX` |
| Google Ads conversions | Conversion Linker + `AW-XXXXXXXXX` |
| Floodlight | Conversion Linker + advertiser id |

The creator agent reads this and refuses to build event tags on a foundation
that does not exist.

## 6. Respect the GA4 platform limits

- Event name: up to 40 characters, `a-z`, `0-9` and `_`, starting with a letter.
- Up to 25 parameters per event.
- Parameter name: up to 40 characters. Text value: up to 100 characters (500 on
  360 properties).
- Up to 25 user properties per GA4 property.
- Reserved prefixes: `_`, `ga_`, `google_`, `firebase_`, `gtag`.
- Reserved names you cannot reuse: `first_open`, `first_visit`,
  `session_start`, `user_engagement`, `app_exception`, `in_app_purchase`,
  `screen_view`, among others.

Put these limits in the client's document. They are the most common cause of a
silently dropped event.

## 7. Prefer the official standard over a custom event

Before creating `purchase_completed`, check whether `purchase` covers it.
Google's recommended events feed built-in reports (Monetization, Lead
generation) and Google Ads integrations. An equivalent custom event loses all
of that and still needs a custom dimension to be analysed.

Document the decision whenever you leave the standard, with the reasoning.

## 8. Version and date it

Every document opens with:

```markdown
> Version 1.0 - updated 2026-08-24 - owner: <name>
```

Without a date, nobody can tell whether the document or the container is the
one that is wrong.

## 9. End with "Open questions"

A list of what is still undecided, who decides, and by when. Documentation that
is honest about what it does not know beats documentation that is complete and
wrong.
