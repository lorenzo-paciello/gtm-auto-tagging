# Measuring usage, and testing against real workspaces

Two things this page covers: how to see what the agent actually spends per run,
and how to exercise every flow against the two container states that matter —
empty, and neglected.

## Where the numbers come from

`gtm_agent/usage.py` registers a `UsageTrackerPlugin` on the ADK `App`, so it
sees every sub agent without each one opting in. It appends one JSON line per
model call to `usage/model_calls.jsonl`:

```json
{"ts": 1756..., "run_id": "a1b2c3d4e5f6", "agent": "auditor_agent",
 "model": "gemini-3.1-flash-lite", "latency_s": 2.41,
 "prompt_tokens": 18420, "output_tokens": 612, "cached_tokens": 0,
 "total_tokens": 19032, "error": null}
```

Nothing is aggregated at write time, so a run that dies mid-way still leaves
usable data. Streamed partial chunks are skipped — only the final chunk carries
usage, and counting the partials would inflate the request count several-fold.

## Reading it

```powershell
.venv\Scripts\python.exe -m gtm_agent.usage           # every run
.venv\Scripts\python.exe -m gtm_agent.usage --last    # the most recent run
.venv\Scripts\python.exe -m gtm_agent.usage --json    # for a spreadsheet
```

The report breaks totals down **by agent** and **by model**, plus a
requests-per-run figure.

## What to do with each number

| Symptom | Likely cause | Lever |
| --- | --- | --- |
| Hitting a **requests-per-day** cap | one user turn costs many calls — every sub agent transfer and every tool round trip is its own request | fewer transfers: ask one specialist directly instead of a compound request |
| Hitting a **tokens-per-minute** cap in bursts | the auditor fans out across several large tool results in quick succession | run audits on their own; the API client already backs off on 429 |
| High **prompt tokens**, few requests | instructions plus tool declarations dominate, and they are resent on every call of that agent | trim that agent's toolset — declarations cost more than replies |
| One **agent** dwarfs the rest | it is doing the heavy reasoning | point only that role at a stronger model via `GTM_MODEL_REASONING`, leave `GTM_MODEL_FAST` cheap |

The single most useful line is `requests per run`. Free-tier quotas are counted
in requests, not tokens, so that number times your runs per day is what has to
fit under the cap.

## Spikes and quota on a free tier

- The Tag Manager API allows roughly 0.25 queries/second per user. The client
  retries 429s with exponential backoff (4 attempts), so a burst appears as
  latency rather than failure.
- Model quotas are separate and per model. `gemini-3.1-flash-lite` has a far
  larger daily request allowance than the bigger models — this is why both
  model roles default to it.
- `GTM_DRY_RUN=true` exercises the whole planning path, including validation,
  without any write call. Use it when iterating on prompts.

---

# Testing every flow

Two workspaces, kept side by side, cover the range of real containers. Create
both in the same container so switching is one `.env` edit.

```
GTM_WORKSPACE_ID=<id>
```

## Workspace A — empty

Tests that the agent builds a foundation in the right order instead of
assuming one.

| Ask | What should happen |
| --- | --- |
| "What's in my container?" | reports an empty container without inventing structure |
| "Audit my container" | not "no issues" — an empty container has no base tag, no consent, no coverage |
| "Create the GA4 purchase event" | `check_tagging_prerequisites` blocks, the Google Tag is proposed first, the measurement id constant is created before the tags reference it |
| "Create a TikTok purchase tag" | stops and asks you to install the template — the API cannot |
| "Organize the workspace" | says there is nothing to organize |

Red flags: a tag created before its variable; a "base tag" with a blank event
name; an audit that reports the container as healthy.

## Workspace B — deliberately neglected

Seed it with the states worth catching. Each row is a real failure mode:

| Seed | Should be reported as |
| --- | --- |
| Two Google Tags, same `G-` id | critical — duplicate base tag double-counts every page view |
| A Google Tag for `G-` only, plus Google Ads conversions | high — no `AW-` destination |
| A `gaawe` with a literal id no Google Tag configures | critical — `destination_without_base_tag` |
| `CONST - X ID` created, tags referencing `CONST - X id` | critical — `reference_near_miss`, repoint the tags, do not create a second variable |
| A tag with no firing trigger | critical — never executes |
| A Meta/Pinterest tag with a blank event name | not a base tag — a broken event tag |
| A CMP firing on All Pages instead of Consent Initialization | recommended — runs too late |
| A paused tag with no note | low |
| Everything outside folders | medium |
| One pixel installed twice: once as a template, once as Custom HTML | critical — the commonest duplication there is, and listing by type never shows it |
| A `gaawe` named `page_view` beside a Google Tag for the same property | the page view is counted twice; no base-tag comparison finds this one |
| Two Google Ads conversions with the same id and label, on different triggers | the same conversion action counted twice |

Then ask, in order:

1. **"Audit my container"** — compare the report against the table above. Every
   row should appear with the stated severity. A row that is missing is a gap
   worth reporting.
2. **"Fix the critical findings"** — the fixes should be ordered: variables
   before the tags that use them, base tags before event tags.
3. **"Organize the workspace"** — folders by media, nothing invented.
4. **"Audit again"** — the same findings must not reappear.
5. **Try to create a duplicate on purpose** — ask for a tag you know already
   exists: the same Meta pixel, the same Google Ads conversion, a `page_view`
   event for a property whose Google Tag already sends it. Each must come back
   **refused, with nothing written**, naming the existing tag. Then ask again
   and approve it: it should be created and the reason recorded in the notes.
   A duplicate that is created and only then reported is the failure this check
   exists to prevent.

Between steps 1 and 4, run:

```powershell
.venv\Scripts\python.exe -m gtm_agent.usage --last
```

That gives you the cost of one full audit-fix-organize cycle, which is the
number to plan a day's quota around.

## What "the audit is the source of truth" means in practice

The audit is complete when every one of these returns `clean` or an explained
finding:

```
check_tagging_prerequisites(product="all")
find_duplicate_tags()
find_broken_references()
check_id_consistency()
get_container_snapshot()          # insights
get_workspace_status()            # what is pending publication
```

If the agent reports "no issues" for a category without having called the
matching tool, that is a bug in the report, not a healthy container. The
auditor's instructions forbid it explicitly; if you see it, the prompt needs
tightening rather than the container.
