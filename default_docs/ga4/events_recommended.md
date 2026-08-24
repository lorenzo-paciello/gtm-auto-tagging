# GA4 - eventos recomendados

Eventos com nome e parametros definidos pelo Google. Usa-los libera relatorios
prontos e integracoes (Google Ads, Search Ads 360) que um evento customizado
equivalente nao ativa.

**Regra do projeto:** so crie evento customizado depois de confirmar que nao ha
recomendado equivalente, e documente a justificativa.

## Todas as propriedades

| Evento | Quando | Parametros |
| --- | --- | --- |
| `login` | usuario faz login | `method` |
| `sign_up` | usuario cria conta | `method` |
| `search` | busca interna no site | `search_term` |
| `select_content` | seleciona um conteudo | `content_type`, `content_id` |
| `share` | compartilha conteudo | `method`, `content_type`, `item_id` |
| `join_group` | entra em um grupo/comunidade | `group_id` |
| `tutorial_begin` | inicia um tutorial | - |
| `tutorial_complete` | conclui um tutorial | - |
| `generate_lead` | envia formulario de contato/orcamento | `currency`, `value`, `lead_source` |
| `qualify_lead` | lead qualificado pelo time comercial | `currency`, `value` |
| `working_lead` | lead em atendimento | `currency`, `value`, `lead_status` |
| `close_convert_lead` | lead convertido em cliente | `currency`, `value` |
| `close_unconvert_lead` | lead perdido | `currency`, `value`, `unconvert_lead_reason` |
| `disqualify_lead` | lead desqualificado | `currency`, `value`, `disqualified_lead_reason` |

> `currency` e obrigatorio sempre que `value` for enviado. Sem `currency`, o
> GA4 ignora o valor. Formato ISO 4217 (`BRL`, `USD`).

## Ecommerce

Ver `ga4/events_ecommerce.md` - funil completo, array `items` e ordem de
disparo.

## Jogos

| Evento | Parametros |
| --- | --- |
| `earn_virtual_currency` | `virtual_currency_name`, `value` |
| `spend_virtual_currency` | `virtual_currency_name`, `value`, `item_name` |
| `level_start` | `level_name` |
| `level_end` | `level_name`, `success` |
| `level_up` | `level`, `character` |
| `post_score` | `score`, `level`, `character` |
| `unlock_achievement` | `achievement_id` |

## Viagens

| Evento | Parametros |
| --- | --- |
| `view_search_results` | `search_term` |
| `select_item` | `items`, `item_list_name`, `item_list_id` |
| `view_item` | `currency`, `value`, `items` |
| `add_to_cart` / `begin_checkout` / `purchase` | mesma estrutura de ecommerce |

## Emprego / educacao

| Evento | Parametros |
| --- | --- |
| `view_job` / `apply_job` | `job_id`, `job_title` |
| `view_course` / `enroll_course` | `course_id`, `course_name` |

## Parametros de negocio frequentes (customizados)

Nao sao oficiais, mas sao o padrao de mercado. Se usar, registre como dimensao
personalizada:

| Parametro | Escopo | Uso |
| --- | --- | --- |
| `user_id` | usuario (campo nativo) | id interno, nunca PII |
| `customer_type` | usuario | novo / recorrente |
| `logged_in` | usuario | `true` / `false` |
| `form_name` | evento | identifica o formulario em `generate_lead` |
| `cta_text` | evento | texto do botao em `select_content` |
| `page_type` | evento | home / categoria / produto / checkout |
| `error_message` | evento | mensagem de erro de validacao |

## Marcar como conversao (key event)

No GA4, "conversao" passou a se chamar **key event**. Marcar acontece na
interface (Admin > Eventos), nao na tag. O agente deve lembrar o usuario disso
apos criar um evento de negocio - a tag sozinha nao cria a conversao.

Eventos tipicamente marcados: `purchase`, `generate_lead`, `sign_up`,
`begin_checkout` (opcional), `qualify_lead`.
