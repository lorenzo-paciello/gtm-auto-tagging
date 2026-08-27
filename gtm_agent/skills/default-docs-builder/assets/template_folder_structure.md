# Container folder structure - <BUSINESS NAME>

> Version 1.0 - updated <YYYY-MM-DD> - owner: <NAME>

## Chosen criterion

- [ ] By **media / tool** (recommended default)
- [ ] By **function / journey**
- [ ] Hybrid: <describe>

Reasoning: <why this criterion fits this container>

## Folders

| Folder | What goes in | What does NOT |
| --- | --- | --- |
| `GA4` | GA4 event and configuration tags, triggers and variables exclusive to GA4 | variables shared with other media |
| `Google Ads` | conversion, remarketing, conversion linker | |
| `Floodlight` | counter and sales | |
| `<Paid media>` | pixels and conversions for <tool> | |
| `Consent` | CMP, Consent Mode, Conversion Linker | |
| `Utilities` | variables and triggers used by more than one media | any tag |
| `Deprecated` | paused entities awaiting removal | |

## Rules

1. An entity belongs to exactly one folder.
2. An entity used by two or more media goes to `Utilities`.
3. Every new tag is born in a folder.
4. A folder empty for more than one review cycle should be removed.
5. Do not create folders per person, date or project.

## Current state

| Folder | Tags | Triggers | Variables |
| --- | --- | --- | --- |
| | | | |

## Open questions

| Item | Who decides | By when |
| --- | --- | --- |
| | | |
