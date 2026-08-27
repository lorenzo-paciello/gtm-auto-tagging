# Container folder structure (project standard)

The criterion used by `container_organizer_agent`.

> To adopt a different criterion, create
> `custom_docs/conventions/folder_structure.md`.

## Primary criterion: by media / tool

This is the criterion that survives time best. Tools enter and leave a
container as a block (the contract with media vendor X ended, remove folder X);
business functions spread across several tools.

| Folder | What goes in | What does NOT |
| --- | --- | --- |
| `Google Tag` | the `googtag` base tag and its configuration variables | events |
| `GA4` | `gaawe` tags, triggers and variables exclusive to GA4 | shared variables |
| `Google Ads` | `awct`, `sp`, `gclidw` and conversion variables | |
| `Floodlight` | `flc`, `fls` and activity variables | |
| `<Paid media>` | Meta, LinkedIn, TikTok pixels and events, one folder per tool | |
| `Consent` | CMP, Consent Mode, consent initialization triggers | |
| `Utilities` | variables and triggers used by **two or more** folders | any tag |
| `Third parties` | chat, A/B testing, heatmaps, scripts with no media category | |
| `Deprecated` | paused entities awaiting removal | |

## Alternative criterion: by function / journey

Use it when the container has a single dominant tool (typically GA4 only) and
more than 60 tags.

| Folder | Contents |
| --- | --- |
| `Base` | configuration, consent, linker |
| `Ecommerce` | the `view_item` -> `purchase` funnel |
| `Forms` | `generate_lead`, `form_start`, `form_submit` |
| `Engagement` | scroll, video, download, clicks |
| `Account` | `login`, `sign_up` |
| `Utilities` | shared |

## Rules

1. **One entity, one folder.** GTM does not allow two.
2. **Shared goes to `Utilities`.** A `DLV - ecommerce` used by GA4, Google Ads
   and Floodlight belongs to none of the three.
3. **Every new tag is born in a folder.** `parentFolderId` set at creation
   time, not afterwards.
4. **Never create folders per person, date, project or sprint.** They go stale
   in weeks.
5. **Never create near-duplicate names.** `GA4` and `GA 4` in the same list is
   a disaster. Check `list_folders` before creating.
6. **Empty folders should be removed** at the next review.
7. Triggers and variables exclusive to a tool follow that tool's folder. Only
   genuinely shared items move out.

## When folders stop being enough

Past roughly 150 tags, folders are a stopgap. Consider:

- splitting containers by domain or by business area;
- moving collection to a server-side container;
- using zones (GTM 360) to delegate parts of the container to different teams.

Record the recommendation in the audit instead of creating a twentieth folder.
