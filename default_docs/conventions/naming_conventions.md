# Convencoes de nomenclatura (padrao do projeto)

Padrao usado pelo `tags_creator_agent` ao criar entidades e pelo
`container_organizer_agent` ao propor renomeacoes.

> Para adotar outro padrao, crie `custom_docs/conventions/naming_conventions.md`.
> Ele sobrepoe este arquivo.

## Principio

O nome responde tres perguntas sem abrir a entidade: **qual ferramenta**,
**que tipo de coisa e**, **o que faz**.

## Tags

```
<FERRAMENTA> - <TIPO> - <DESCRICAO>
```

| Exemplo | Leitura |
| --- | --- |
| `GA4 - Event - purchase` | evento de compra no GA4 |
| `GA4 - Event - generate_lead` | evento de lead no GA4 |
| `Google Tag - GA4 + Ads` | tag base do Google |
| `Google Ads - Conversion - Compra` | conversao de compra |
| `Google Ads - Remarketing - Global` | remarketing |
| `Google Ads - Conversion Linker` | conversion linker |
| `Floodlight - Sales - Compra` | floodlight de venda |
| `Floodlight - Counter - Lead` | floodlight de contagem |
| `Meta - Pixel - Base` | pixel base do Meta |
| `Meta - Event - Purchase` | evento do Meta |
| `Custom HTML - Chat Widget` | script de terceiro sem template |

Contra-exemplos (nao use): `ga4 purchase`, `Tag de compra`,
`GA4_Event_Purchase`, `[GA4] purchase`, `Tag 12`, `purchase - joao`.

## Acionadores

```
<PREFIXO> - <CONDICAO>
```

| Prefixo | Tipo | Exemplo |
| --- | --- | --- |
| `CE` | evento personalizado | `CE - purchase` |
| `PV` | pageview | `PV - Checkout` |
| `DOM` | DOM ready | `DOM - Todas as paginas` |
| `WIN` | window loaded | `WIN - Home` |
| `CLK` | clique | `CLK - Botao Comprar` |
| `LINK` | clique em link | `LINK - Saida externa` |
| `FORM` | envio de formulario | `FORM - Contato` |
| `VIS` | visibilidade | `VIS - Banner Home` |
| `SCROLL` | rolagem | `SCROLL - 75% Blog` |
| `TIMER` | cronometro | `TIMER - 30s` |
| `HIST` | mudanca de historico | `HIST - SPA` |
| `INIT` | inicializacao | `INIT - Consentimento` |
| `EXC` | excecao / bloqueio | `EXC - Homologacao` |
| `GRP` | grupo de acionadores | `GRP - Consentimento + Pageview` |

Para eventos GA4, o nome do evento entra **exatamente como esta no dataLayer**:
`CE - add_to_cart`, nunca `CE - Adicionar ao carrinho`.

## Variaveis

```
<PREFIXO> - <FONTE>
```

| Prefixo | Tipo (`type`) | Exemplo |
| --- | --- | --- |
| `DLV` | `v` - camada de dados | `DLV - ecommerce.transaction_id` |
| `CONST` | `c` - constante | `CONST - GA4 Measurement ID` |
| `CJS` | `jsm` - JavaScript personalizado | `CJS - Normaliza Email` |
| `JS` | `j` - variavel JavaScript | `JS - document.title` |
| `URL` | `u` - URL | `URL - utm_source` |
| `COOKIE` | `k` - cookie proprio | `COOKIE - user_id` |
| `DOM` | `d` - elemento DOM | `DOM - Preco do produto` |
| `LT` | `smm` - tabela de pesquisa | `LT - Ambiente por Hostname` |
| `RT` | `remm` - tabela regex | `RT - Tipo de pagina por URL` |
| `AEV` | `aev` - evento automatico | `AEV - Click Text` |

Em `DLV`, use o caminho real do dataLayer no nome: `DLV - ecommerce.value` diz
o que a variavel le; `DLV - Valor` nao diz nada.

## Pastas

Nome curto, sem prefixo: `GA4`, `Google Ads`, `Floodlight`, `Meta`,
`Consentimento`, `Utilitarios`, `Depreciado`. Ver
`conventions/folder_structure.md`.

## Regras gerais

1. Separador ` - ` (espaco, hifen, espaco). Nunca `_`, `|`, `/` ou `::`.
2. Sem acentos e sem caracteres especiais nos nomes de entidade.
3. Sem numeracao sequencial, sem data, sem nome de pessoa.
4. Ambiente, quando existir, vai no fim entre colchetes:
   `GA4 - Event - purchase [STG]`.
5. Toda entidade critica tem `notes` com: requisito de origem, data e
   responsavel.
6. Nomes sao unicos dentro de cada tipo. Nome duplicado e achado de auditoria.

## Nota sobre renomear

Renomear uma **variavel** nao atualiza as referencias `{{Nome antigo}}` dentro
de tags e acionadores. A referencia orfa passa a devolver string vazia, sem
erro visivel. Antes de renomear qualquer variavel: liste onde ela e usada,
atualize as referencias e so entao renomeie.

Renomear tags, acionadores e pastas e seguro - as referencias sao por id.
