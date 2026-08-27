# GA4 - automatic and enhanced measurement events

Events GA4 collects with no extra tag. **Do not build a tag for any of them.**
Creating a `gaawe` tag with `eventName: page_view` alongside the Google Tag is
the most common cause of duplicated page views in a GTM container.

## Automatically collected (web)

| Event | When it fires | Relevant parameters |
| --- | --- | --- |
| `first_visit` | the user's first visit to the site | - |
| `session_start` | a session begins | - |
| `user_engagement` | user active for >= 10s, with a conversion or >= 2 page views | `engagement_time_msec` |
| `page_view` | page load (from the Google Tag / GA4 config) | `page_location`, `page_referrer`, `page_title` |

## Enhanced measurement

Enabled in the GA4 UI, under Data streams. Each item can be toggled
individually.

| Event | Trigger | Parameters |
| --- | --- | --- |
| `page_view` | page load and, if enabled, history change (SPA) | `page_location`, `page_referrer`, `page_title` |
| `scroll` | 90% vertical scroll, once per page | `percent_scrolled` (always 90) |
| `click` | click on a link leaving the domain | `link_classes`, `link_domain`, `link_id`, `link_url`, `outbound` |
| `view_search_results` | URL carries a search parameter (`q`, `s`, `search`, `query`, `keyword`) | `search_term` |
| `video_start` | embedded YouTube video starts, JS API enabled | `video_current_time`, `video_duration`, `video_percent`, `video_provider`, `video_title`, `video_url`, `visible` |
| `video_progress` | 10%, 25%, 50%, 75% of the video | same |
| `video_complete` | video ends | same |
| `file_download` | click on a document, text, executable, presentation, video or audio link | `file_extension`, `file_name`, `link_classes`, `link_id`, `link_text`, `link_url` |
| `form_start` | first interaction with a form in the session | `form_id`, `form_name`, `form_destination` |
| `form_submit` | form submission | `form_id`, `form_name`, `form_destination`, `form_submit_text` |

### Decision: enhanced measurement or GTM?

| Situation | Recommendation |
| --- | --- |
| Simple brochure site | use enhanced measurement |
| You need extra parameters on the event (e.g. form category) | turn the item off in GA4 and implement it in GTM |
| SPA with complex routing | turn off "History changes" and control `page_view` from GTM |
| Forms inside an iframe or with AJAX validation | native `form_submit` will not catch them; implement in GTM |

Never leave both enabled for the same event. Check this during an audit: a GTM
`form_submit` tag while enhanced measurement's form tracking is on produces
double counting.

## Automatically collected (app - Firebase)

Relevant for app containers or properties with both web and app streams:
`first_open`, `app_update`, `app_remove`, `app_exception`,
`app_store_subscription_*`, `in_app_purchase`, `notification_*`, `os_update`,
`screen_view`.

## How to spot duplication in an audit

1. List the container's `gaawe` tags.
2. Flag every tag whose `eventName` appears in the table above.
3. Check in GA4 whether the matching enhanced measurement item is on.
4. If both are active, that is a critical finding.
