# GA4 - limits, reserved names and naming rules

Platform rules. Breaking any of them makes GA4 drop the event or the parameter
**silently** - no error in Preview, no warning in the UI.

## Event names

| Rule | Value |
| --- | --- |
| Allowed characters | letters, numbers and `_` |
| First character | must be a letter |
| Maximum length | 40 characters |
| Case | case-sensitive - `Purchase` != `purchase`. Always use lowercase |
| Spaces | not allowed |
| Distinct events per property | 500 |

## Parameters

| Rule | Value |
| --- | --- |
| Parameters per event | up to 25 (beyond the automatic ones) |
| Name length | 40 characters |
| Text value length | 100 characters (500 on 360 properties) |
| Event-scoped custom dimensions | 50 (125 on 360) |
| Custom metrics | 50 (125 on 360) |
| Item-scoped dimensions | 10 (25 on 360) |

Every custom parameter must be registered as a **custom dimension or metric**
in GA4 to appear in a report. A parameter that is sent but not registered is
only reachable in BigQuery and the realtime report.

## User properties

| Rule | Value |
| --- | --- |
| Properties per GA4 property | 25 |
| Name length | 24 characters |
| Value length | 36 characters |

## Reserved prefixes

Never use as a prefix for an event, parameter or user property:

- `_` (underscore)
- `ga_`
- `google_`
- `firebase_`
- `gtag`

## Reserved event names

These cannot be reused for custom events:

`ad_activeview`, `ad_click`, `ad_exposure`, `ad_impression`, `ad_query`,
`ad_reward`, `adunit_exposure`, `app_background`, `app_clear_data`,
`app_exception`, `app_install`, `app_remove`, `app_store_refund`,
`app_store_subscription_cancel`, `app_store_subscription_convert`,
`app_store_subscription_renew`, `app_update`, `app_upgrade`,
`dynamic_link_app_open`, `dynamic_link_app_update`,
`dynamic_link_first_open`, `error`, `firebase_campaign`,
`firebase_in_app_message_action`, `firebase_in_app_message_dismiss`,
`firebase_in_app_message_impression`, `first_open`, `first_visit`,
`in_app_purchase`, `notification_dismiss`, `notification_foreground`,
`notification_open`, `notification_receive`, `os_update`, `screen_view`,
`session_start`, `user_engagement`.

## Reserved parameter names

`firebase_conversion`, `engagement_time_msec`, `session_id`, `ga_session_id`,
`ga_session_number`, `page_title`, `page_location`, `page_referrer` (the last
three can be deliberately overridden on the tag, but never repurposed to mean
something else).

## Event naming best practices

1. **Verb + object**, in English and `snake_case`: `add_to_cart`,
   `generate_lead`, `view_item`.
2. **Never put a dimension in the event name.** Wrong: `purchase_mobile`,
   `purchase_desktop`. Right: `purchase` with a `device_category` parameter.
   Each variant in the name burns one of the 500 event slots and makes the
   total impossible to sum.
3. **Do not translate.** A localized event name breaks the built-in
   Monetization reports and conversion import into Google Ads.
4. **Reuse the recommended event** before creating a custom one. See
   `ga4/events_recommended.md`.

## Quick check before creating an event

- [ ] Is there an equivalent automatic or recommended event?
- [ ] Does the name fit 40 characters, `snake_case`, no reserved prefix?
- [ ] Will the custom parameters be registered as dimensions/metrics?
- [ ] Does every text value fit in 100 characters?
- [ ] Does the event represent an action, not a segmentation?
