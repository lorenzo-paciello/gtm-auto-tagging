# GA4 - ecommerce

The official funnel. The Monetization reports depend on these exact names and
on the `items` array.

## Funnel and firing order

| # | Event | When | Event parameters |
| --- | --- | --- | --- |
| 1 | `view_item_list` | a product list / shelf is shown | `item_list_id`, `item_list_name`, `items` |
| 2 | `select_item` | a product in the list is clicked | `item_list_id`, `item_list_name`, `items` |
| 3 | `view_item` | product detail page | `currency`, `value`, `items` |
| 4 | `add_to_wishlist` | added to the wishlist | `currency`, `value`, `items` |
| 5 | `add_to_cart` | added to the cart | `currency`, `value`, `items` |
| 6 | `view_cart` | cart is viewed | `currency`, `value`, `items` |
| 7 | `remove_from_cart` | removed from the cart | `currency`, `value`, `items` |
| 8 | `begin_checkout` | checkout starts | `currency`, `value`, `coupon`, `items` |
| 9 | `add_shipping_info` | shipping option chosen | `currency`, `value`, `coupon`, `shipping_tier`, `items` |
| 10 | `add_payment_info` | payment method chosen | `currency`, `value`, `coupon`, `payment_type`, `items` |
| 11 | `purchase` | order confirmed | `transaction_id`, `value`, `currency`, `tax`, `shipping`, `coupon`, `items` |
| 12 | `refund` | full or partial refund | `transaction_id`, `value`, `currency`, `items` (partial) |

Complementary: `view_promotion` and `select_promotion`, with `promotion_id`,
`promotion_name`, `creative_name`, `creative_slot`.

## The `items` array

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `item_id` | string | yes* | SKU. *Required if `item_name` is absent |
| `item_name` | string | yes* | *Required if `item_id` is absent |
| `affiliation` | string | no | store or seller |
| `coupon` | string | no | item-level coupon |
| `discount` | number | no | unit discount, in currency |
| `index` | number | no | position in the list (1-based) |
| `item_brand` | string | no | |
| `item_category` .. `item_category5` | string | no | category hierarchy |
| `item_list_id` / `item_list_name` | string | no | source list |
| `item_variant` | string | no | colour, size |
| `location_id` | string | no | Google Place ID |
| `price` | number | no | unit price, no currency symbol |
| `quantity` | number | no | defaults to 1 |

Limit: **200 items** per event. `price` and `value` are numbers, never
formatted strings (`"$459.90"` breaks collection).

## Keeping `value` consistent

`value` should be the sum of `price * quantity` across the items. A mismatch
between `value` and the `items` array is a critical audit finding: GA4 uses
`value` for revenue and `items` for the product reports, and they end up
disagreeing.

On `purchase`, whether `value` **includes** shipping and tax depends on how the
business defines revenue; `tax` and `shipping` are sent separately either way.
Record the choice in `custom_docs/`.

## dataLayer

Always clear the `ecommerce` object before each event so values do not leak
from the previous one:

```javascript
dataLayer.push({ ecommerce: null });
dataLayer.push({
  event: "purchase",
  ecommerce: {
    transaction_id: "ORD-100294",
    value: 459.90,
    tax: 12.50,
    shipping: 19.90,
    currency: "USD",
    coupon: "FIRSTORDER",
    items: [
      {
        item_id: "SKU-1",
        item_name: "Basic tee",
        item_brand: "Brand",
        item_category: "Apparel",
        item_variant: "Black / M",
        price: 89.90,
        quantity: 2,
        index: 1
      }
    ]
  }
});
```

## GTM implementation

1. **Variable** `DLV - ecommerce` (Data Layer Variable, version 2) pointing at
   `ecommerce`.
2. **Trigger** one custom event trigger per event (`CE - purchase`).
3. **Tag** a GA4 Event tag (`gaawe`) with `eventName` matching the event and
   the "Send Ecommerce data" option reading from the Data Layer.
4. Parameters such as `transaction_id` and `value` are read from the
   `ecommerce` object automatically when that option is on -- do not repeat
   them by hand in the event parameter table.

## Preventing duplicate purchases

`purchase` firing more than once per order is the most expensive ecommerce
error. Check in an audit:

- [ ] Does the trigger fire "once per event" rather than "once per page"?
- [ ] Is the success page reachable by refresh (F5)?
- [ ] Is `transaction_id` always present? Without it GA4 cannot deduplicate.
- [ ] In an SPA, does the event refire on back navigation?
