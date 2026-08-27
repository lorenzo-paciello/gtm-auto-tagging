# Custom documentation

Put your business's tagging documentation here. Files in this directory
**override** their counterparts in `default_docs/` when they share the same
relative path.

Examples:

| File | Effect |
| --- | --- |
| `custom_docs/conventions/naming_conventions.md` | replaces the project naming standard |
| `custom_docs/ga4/events_my_store.md` | adds your own event dictionary |
| `custom_docs/ga4/events_ecommerce.md` | replaces the default ecommerce funnel |

## How to create them

Ask the agent: *"I want to create my standard tagging documentation."* It loads
the `default-docs-builder` skill, interviews you, drafts the Markdown, shows it
for approval, and saves it here.

You can also write the files by hand -- they are plain Markdown. The agents
read every `.md` in this directory, at any subfolder depth.
