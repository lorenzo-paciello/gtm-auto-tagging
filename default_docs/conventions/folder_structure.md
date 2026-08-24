# Estrutura de pastas do container (padrao do projeto)

Criterio usado pelo `container_organizer_agent`.

> Para adotar outro criterio, crie `custom_docs/conventions/folder_structure.md`.

## Criterio primario: por midia / ferramenta

E o criterio que sobrevive melhor ao tempo. Ferramentas entram e saem do
container em bloco (encerrou o contrato com a midia X, remove-se a pasta X);
funcoes de negocio se espalham por varias ferramentas.

| Pasta | O que entra | O que NAO entra |
| --- | --- | --- |
| `Google Tag` | tag base `googtag` e suas variaveis de configuracao | eventos |
| `GA4` | tags `gaawe`, acionadores e variaveis exclusivos de GA4 | variaveis compartilhadas |
| `Google Ads` | `awct`, `sp`, `gclidw` e variaveis de conversao | |
| `Floodlight` | `flc`, `fls` e variaveis de activity | |
| `<Midia paga>` | pixels e eventos de Meta, LinkedIn, TikTok etc., uma pasta por ferramenta | |
| `Consentimento` | CMP, Consent Mode, acionadores de inicializacao de consentimento | |
| `Utilitarios` | variaveis e acionadores usados por **duas ou mais** pastas | qualquer tag |
| `Terceiros` | chats, testes A/B, heatmaps, scripts sem categoria de midia | |
| `Depreciado` | entidades pausadas aguardando remocao | |

## Criterio alternativo: por funcao / jornada

Use quando o container tem uma unica ferramenta dominante (tipicamente so GA4)
e mais de 60 tags.

| Pasta | Conteudo |
| --- | --- |
| `Base` | configuracao, consentimento, linker |
| `Ecommerce` | funil `view_item` -> `purchase` |
| `Formularios` | `generate_lead`, `form_start`, `form_submit` |
| `Engajamento` | scroll, video, download, cliques |
| `Conta` | `login`, `sign_up` |
| `Utilitarios` | compartilhados |

## Regras

1. **Uma entidade, uma pasta.** O GTM nao permite duas.
2. **Compartilhado vai para `Utilitarios`.** Uma `DLV - ecommerce` usada por
   GA4, Google Ads e Floodlight nao pertence a nenhuma das tres.
3. **Toda tag nova nasce em uma pasta.** `parentFolderId` preenchido na
   criacao, nao depois.
4. **Nao crie pastas por pessoa, data, projeto ou sprint.** Elas envelhecem em
   semanas.
5. **Nao crie nomes proximos.** `GA4` e `GA 4` na mesma lista sao um desastre.
   Cheque `list_folders` antes de criar.
6. **Pasta vazia deve ser removida** na proxima revisao.
7. Acionadores e variaveis exclusivos de uma ferramenta acompanham a pasta
   dela. So o que e realmente compartilhado sai.

## Quando a pasta nao resolve

Se o container passa de ~150 tags, pasta vira paliativo. Considere:

- separar containers por dominio ou por area de negocio;
- mover a coleta para um container server-side;
- usar zonas (GTM 360) para delegar partes do container a times distintos.

Registre a recomendacao na auditoria em vez de criar uma vigesima pasta.
