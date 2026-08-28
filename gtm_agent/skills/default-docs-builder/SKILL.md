---
name: default-docs-builder
description: Guides the user through writing their own standard tagging documentation (events, parameters, naming, folder structure) and saves the files into custom_docs/, which takes precedence over the project's default documentation. Use it when the user wants to create, review, extend or replace the standard documentation the agents follow - for example "I want to define my own event dictionary", "my company uses a different naming convention", "document the tagging for my site".
metadata:
  adk_additional_tools:
    - save_custom_doc
---

# Standard documentation builder

This skill turns what the user knows about their business into documentation
that the sub agents (`tags_creator_agent`, `container_organizer_agent`,
`auditor_agent`) will treat as the source of truth.

The output is `.md` files in `custom_docs/`. They **override** their
counterparts in `default_docs/`: if the user defines their own
`naming_conventions.md`, theirs is the one that applies.

## Before you start

Run `list_docs()` and show the user what already exists. New documentation
should complement, not repeat. If the user wants to override a default
document, explain that they only need a file with the **same relative path**
inside `custom_docs/`.

`list_docs`, `read_doc` and `search_docs` are available to the agent at all
times. Activating this skill grants only `save_custom_doc` -- the one tool that
writes.

## Step 1 - Establish the scope

Ask these questions in ONE message, as a list. Do not interrogate the user one
question at a time.

1. What is the business model? (ecommerce, lead generation, media/content,
   SaaS, marketplace, app + web)
2. Which tools are in the container? (GA4, Google Ads, Floodlight/CM360, Meta,
   LinkedIn, TikTok, others)
3. Is there already a naming convention in use? Ask for 3 to 5 real tag names.
4. Which business events matter most? (purchase, lead, sign-up, newsletter
   subscription, filter usage, checkout start)
5. Is anything forbidden or mandatory? (e.g. never send plain email, always
   fill `notes`, always respect Consent Mode)

If the container is reachable, use `search_docs` and ask the root agent for the
current inventory before proposing a convention -- documenting the standard
that already exists costs less than imposing a new one.

## Step 2 - Choose which documents to produce

Propose a minimum set and ask which ones they want now:

| Suggested file | Contents |
| --- | --- |
| `conventions/naming_conventions.md` | naming standard for tags, triggers, variables and folders |
| `conventions/folder_structure.md` | which folders exist and what goes in each |
| `ga4/events_<business>.md` | the business event dictionary: name, when it fires, parameters |
| `ga4/data_layer.md` | the dataLayer contract with the development team |
| `conventions/audit_checklist.md` | what an internal audit must verify |
| `<tool>/<tool>.md` | specifics for Google Ads, Floodlight, Meta, etc. |

Start with the event dictionary: it is the document that changes agent
behaviour the most.

## Step 3 - Write

Load the matching template before writing:

- `load_skill_resource("default-docs-builder", "assets/template_event_dictionary.md")`
- `load_skill_resource("default-docs-builder", "assets/template_naming_conventions.md")`
- `load_skill_resource("default-docs-builder", "assets/template_folder_structure.md")`
- `load_skill_resource("default-docs-builder", "assets/template_audit_checklist.md")`

And read the quality rules in
`load_skill_resource("default-docs-builder", "references/writing_rules.md")`.

Non-negotiable rules while writing:

1. **Every event gets a parameter table** with columns: parameter, type,
   required, dataLayer source, example.
2. **Every event states when it fires**, in business language and in technical
   language (which dataLayer event, which URL, which selector).
3. **GA4 event names follow the platform rules**: `snake_case`, up to 40
   characters, starting with a letter, without the reserved prefixes `ga_`,
   `google_`, `firebase_` and `_`. Prefer Google's recommended names
   (`purchase`, `generate_lead`, `sign_up`) over invented ones -- only create a
   custom event when no official equivalent exists.
4. **Record the foundation.** State which base tag each product depends on, so
   the creator agent can check it. See `read_doc("gtm/prerequisites.md")`.
5. **No generic examples.** Use the real names from the user's business.
6. **Flag what is still open** in a final "Open questions" section instead of
   inventing an answer.

## Step 4 - Review with the user BEFORE saving

Show the complete Markdown in the chat and ask whether you may save it. Do not
call `save_custom_doc` without that explicit confirmation.

## Step 5 - Save

```
save_custom_doc(doc_path="ga4/events_ecommerce.md", content="<full markdown>")
```

- The path is relative to `custom_docs/`. Subfolders are created automatically.
- If the file already exists, the tool returns `already_exists`. Read the
  current one with `read_doc`, show the user the difference, and only then
  repeat the call with `overwrite=true`.
- After saving each file, confirm with `list_docs()` and show the user the
  final path.

## Step 6 - Write the closing summary

There is no "finish" tool. Writing this summary is how the skill ends:

1. The list of files created and what each one governs.
2. Which default documents were overridden, if any.
3. A suggested next step: usually running `auditor_agent` to measure the
   current container against the documentation you just wrote.
