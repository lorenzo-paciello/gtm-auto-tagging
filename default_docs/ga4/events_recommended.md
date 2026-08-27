# GA4 - recommended events

Events whose name and parameters are defined by Google. Using them unlocks
built-in reports and integrations (Google Ads, Search Ads 360) that an
equivalent custom event does not activate.

**Project rule:** only create a custom event after confirming no recommended
equivalent exists, and document the reasoning.

## All properties

| Event | When | Parameters |
| --- | --- | --- |
| `login` | user logs in | `method` |
| `sign_up` | user creates an account | `method` |
| `search` | site search | `search_term` |
| `select_content` | a content item is selected | `content_type`, `content_id` |
| `share` | content is shared | `method`, `content_type`, `item_id` |
| `join_group` | joins a group / community | `group_id` |
| `tutorial_begin` | starts a tutorial | - |
| `tutorial_complete` | finishes a tutorial | - |
| `generate_lead` | submits a contact / quote form | `currency`, `value`, `lead_source` |
| `qualify_lead` | lead qualified by sales | `currency`, `value` |
| `working_lead` | lead being worked | `currency`, `value`, `lead_status` |
| `close_convert_lead` | lead converted to customer | `currency`, `value` |
| `close_unconvert_lead` | lead lost | `currency`, `value`, `unconvert_lead_reason` |
| `disqualify_lead` | lead disqualified | `currency`, `value`, `disqualified_lead_reason` |

> `currency` is required whenever `value` is sent. Without `currency`, GA4
> ignores the value. Use ISO 4217 codes (`USD`, `EUR`, `BRL`).

## Ecommerce

See `ga4/events_ecommerce.md` for the full funnel, the `items` array and the
firing order.

## Games

| Event | Parameters |
| --- | --- |
| `earn_virtual_currency` | `virtual_currency_name`, `value` |
| `spend_virtual_currency` | `virtual_currency_name`, `value`, `item_name` |
| `level_start` | `level_name` |
| `level_end` | `level_name`, `success` |
| `level_up` | `level`, `character` |
| `post_score` | `score`, `level`, `character` |
| `unlock_achievement` | `achievement_id` |

## Travel

| Event | Parameters |
| --- | --- |
| `view_search_results` | `search_term` |
| `select_item` | `items`, `item_list_name`, `item_list_id` |
| `view_item` | `currency`, `value`, `items` |
| `add_to_cart` / `begin_checkout` / `purchase` | same structure as ecommerce |

## Jobs / education

| Event | Parameters |
| --- | --- |
| `view_job` / `apply_job` | `job_id`, `job_title` |
| `view_course` / `enroll_course` | `course_id`, `course_name` |

## Common business parameters (custom)

Not official, but they are the de facto market standard. If you use them,
register them as custom dimensions:

| Parameter | Scope | Use |
| --- | --- | --- |
| `user_id` | user (native field) | internal id, never PII |
| `customer_type` | user | new / returning |
| `logged_in` | user | `true` / `false` |
| `form_name` | event | identifies the form on `generate_lead` |
| `cta_text` | event | button text on `select_content` |
| `page_type` | event | home / category / product / checkout |
| `error_message` | event | validation error text |

## Marking as a conversion (key event)

In GA4, "conversion" is now called a **key event**. Marking happens in the UI
(Admin > Events), not on the tag. The agent should remind the user of this
after creating a business event -- the tag alone does not create the
conversion.

Typically marked: `purchase`, `generate_lead`, `sign_up`, `begin_checkout`
(optional), `qualify_lead`.
