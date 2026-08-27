# Model providers

Every agent in this project resolves its model through `gtm_agent/models.py`.
No model name is hardcoded. Switching the whole system to a different provider
is an `.env` change -- no code edits.

## How it works

Agents ask for a **role**, not a model:

| Role | Used by | What it needs to be good at |
| --- | --- | --- |
| `fast` | `tags_listing_agent` | many tool calls, formatting tables. Cheap is fine |
| `reasoning` | root agent, `tags_creator_agent`, `container_organizer_agent`, `auditor_agent` | multi-step planning, JSON payload construction, severity judgement |

Three variables drive everything:

```bash
GTM_MODEL_PROVIDER=google      # google | anthropic | vertex_anthropic | litellm
GTM_MODEL_FAST=...             # model for the fast role
GTM_MODEL_REASONING=...        # model for the reasoning role
GTM_MODEL_MAX_TOKENS=16000     # output cap (Anthropic providers only)
```

If a provider needs a package that is not installed, the agent fails at import
with the exact `pip install` command to run.

---

## Google AI Studio (default)

Free tier available. Best cost per request of the supported options, and the
provider the project was built against.

```bash
GTM_MODEL_PROVIDER=google
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your_key_from_aistudio.google.com

GTM_MODEL_FAST=gemini-3.1-flash-lite
GTM_MODEL_REASONING=gemini-3.1-flash-lite
```

No extra install -- `google-adk` handles Gemini natively.

**Free tier note.** Daily request quotas differ sharply between models. At the
time of writing, `gemini-3.1-flash-lite` allows far more requests per day than
the larger models, which is why it is the default for both roles here. Check
your own quota at [ai.google.dev/pricing](https://ai.google.dev/pricing) before
raising `GTM_MODEL_REASONING` to a bigger model.

| Model | Notes |
| --- | --- |
| `gemini-3.1-flash-lite` | cheapest, most generous free tier |
| `gemini-3.5-flash` | better multi-step planning, much tighter free quota |
| `gemini-3.1-pro-preview` | strongest reasoning, paid tier realistically required |

---

## Anthropic (Claude)

Best fit for the reasoning role: long audit reports, careful JSON construction,
and following a multi-step mandatory workflow without skipping steps.

```bash
pip install anthropic
```

```bash
GTM_MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

GTM_MODEL_FAST=claude-haiku-4-5
GTM_MODEL_REASONING=claude-opus-5
GTM_MODEL_MAX_TOKENS=16000
```

| Model ID | Context | Input $/1M | Output $/1M | Use for |
| --- | --- | --- | --- | --- |
| `claude-opus-5` | 1M | $5.00 | $25.00 | the reasoning role; the default recommendation |
| `claude-sonnet-5` | 1M | $3.00 | $15.00 | reasoning role on a tighter budget |
| `claude-haiku-4-5` | 200K | $1.00 | $5.00 | the fast role |

Use the model ID strings exactly as written -- do not append date suffixes.
Current pricing: [claude.com/pricing](https://claude.com/pricing).

**Why an explicit client.** Passing a bare `"claude-..."` string to ADK's
`Agent(model=...)` routes through ADK's registry to its *Vertex AI* Claude
class, which needs a GCP project. `gtm_agent/models.py` builds `AnthropicLlm`
directly so the Anthropic API is used. That is the reason this project has a
`models.py` at all.

**A mixed setup works too.** Nothing requires both roles to use the same
provider family within Anthropic -- Haiku for listing and Opus for auditing is
the cost-effective pairing.

---

## Claude on Google Cloud Vertex AI

Use this when your billing already runs through GCP. Authentication is GCP
Application Default Credentials, not an Anthropic key.

```bash
pip install "anthropic[vertex]"
gcloud auth application-default login
```

```bash
GTM_MODEL_PROVIDER=vertex_anthropic
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-east5

GTM_MODEL_FAST=claude-haiku-4-5
GTM_MODEL_REASONING=claude-opus-5
```

Vertex pricing is partner-operated and differs from the first-party API:
[cloud.google.com/vertex-ai/generative-ai/pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing#claude-models).

---

## OpenAI, Azure, Ollama, Bedrock and others (LiteLLM)

LiteLLM is the catch-all. The model string carries the provider prefix.

```bash
pip install litellm
```

### OpenAI

```bash
GTM_MODEL_PROVIDER=litellm
OPENAI_API_KEY=sk-...

GTM_MODEL_FAST=openai/gpt-4o-mini
GTM_MODEL_REASONING=openai/gpt-4o
```

### Azure OpenAI

```bash
GTM_MODEL_PROVIDER=litellm
AZURE_API_KEY=...
AZURE_API_BASE=https://your-resource.openai.azure.com
AZURE_API_VERSION=2024-10-21

GTM_MODEL_FAST=azure/your-mini-deployment
GTM_MODEL_REASONING=azure/your-deployment
```

### Ollama (fully local, no API cost)

```bash
ollama pull qwen2.5:14b
```

```bash
GTM_MODEL_PROVIDER=litellm
OLLAMA_API_BASE=http://localhost:11434

GTM_MODEL_FAST=ollama_chat/qwen2.5:7b
GTM_MODEL_REASONING=ollama_chat/qwen2.5:14b
```

Use `ollama_chat/` rather than `ollama/` -- the chat endpoint handles tool
calling far more reliably. Expect to need a 14B model or larger: this project
gives an agent 21 tools and a multi-step mandatory workflow, and small local
models tend to skip steps or emit malformed tool arguments.

### Amazon Bedrock

```bash
GTM_MODEL_PROVIDER=litellm
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=us-east-1

GTM_MODEL_FAST=bedrock/anthropic.claude-haiku-4-5
GTM_MODEL_REASONING=bedrock/anthropic.claude-opus-5
```

Other LiteLLM prefixes ADK routes automatically: `groq/`, `mistral/`,
`deepseek/`, `together_ai/`, `cohere/`, `fireworks_ai/`, `databricks/`,
`ai21/`, `anthropic/`, `vertex_ai/`.

---

## What a model needs to run this project

Before adopting a provider, check it against these. All four are hard
requirements, not preferences:

| Requirement | Why |
| --- | --- |
| **Function calling / tool use** | the agents do nothing but call tools |
| **Parallel or sequential multi-tool turns** | an audit chains 4+ calls before writing a word |
| **Long output** (8K+ tokens) | audit reports and inventory tables are long |
| **Instruction adherence over a long system prompt** | each sub agent prompt is 2-4K tokens of mandatory workflow |

A model that supports tool calling but drifts from a numbered workflow will
skip the prerequisite check and create tags on a missing foundation -- exactly
the failure this project exists to prevent.

## Choosing per role

A practical, cost-aware split:

| Role | Suggestion |
| --- | --- |
| `fast` | the cheapest model in your provider that reliably calls tools |
| `reasoning` | the strongest model you are willing to pay for |

The reasoning role is where quality shows. `tags_creator_agent` builds GTM API
payloads by hand and `auditor_agent` assigns severities -- both degrade
noticeably on a weak model, and both write to or advise on a production
container.

## Adding a provider

`gtm_agent/models.py` has a `_BUILDERS` dictionary mapping provider name to a
builder function. Adding one means adding an entry there and, if it needs a
package, a line in `_EXTRA_DEPENDENCY` so the failure message stays actionable.
Everything else -- agents, tools, prompts -- is provider-agnostic.
