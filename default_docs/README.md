# Documentacao padrao de tagueamento

Fonte da verdade que os agentes do projeto seguem para criar, organizar e
auditar o container GTM. Baseada na documentacao publica do Google para GA4,
Google Ads, Floodlight/CM360 e na API v2 do Tag Manager.

> Estes documentos descrevem o padrao **generico**. Para sobrescrever qualquer
> arquivo daqui com a realidade do seu negocio, crie um arquivo com o **mesmo
> caminho relativo** dentro de `custom_docs/`. A skill `default-docs-builder`
> conduz esse processo.

## Mapa

| Caminho | Conteudo |
| --- | --- |
| `ga4/events_automatically_collected.md` | eventos coletados automaticamente e por medicao aprimorada |
| `ga4/events_recommended.md` | eventos recomendados pelo Google, por vertical |
| `ga4/events_ecommerce.md` | funil de ecommerce completo e o array `items` |
| `ga4/limits_and_naming_rules.md` | limites, nomes reservados e regras de nomenclatura da plataforma |
| `google_ads/conversion_tracking.md` | conversao, remarketing, conversion linker, enhanced conversions |
| `floodlight/floodlight.md` | counter, sales, variaveis customizadas u=, cache buster |
| `gtm/tag_types.md` | `type` de cada tag na API v2 e parametros principais |
| `gtm/trigger_types.md` | `type` de cada acionador e como montar filtros |
| `gtm/variable_types.md` | `type` de cada variavel e seus parametros |
| `conventions/naming_conventions.md` | padrao de nomes de tags, acionadores, variaveis e pastas |
| `conventions/folder_structure.md` | criterio de organizacao em pastas |
| `conventions/audit_checklist.md` | checklist usado pelo `auditor_agent` |

## Precedencia

1. `custom_docs/<caminho>` - documentacao do usuario (vence sempre)
2. `default_docs/<caminho>` - este conjunto
3. Conhecimento geral do modelo - ultimo recurso, e deve ser sinalizado como tal

## Manutencao

As especificacoes do Google mudam. Ao encontrar divergencia entre este texto e
o comportamento real da API ou da interface, a API manda. Registre a correcao
em `custom_docs/` em vez de editar este diretorio, para que uma atualizacao do
projeto nao sobrescreva o ajuste.
