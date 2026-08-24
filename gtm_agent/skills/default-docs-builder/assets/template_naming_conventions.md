# Convencoes de nomenclatura - <NOME DO NEGOCIO>

> Versao 1.0 - atualizado em <AAAA-MM-DD> - responsavel: <NOME>

## Principio

O nome precisa responder, sem abrir a entidade: **qual ferramenta**, **que tipo
de coisa e**, **o que faz**.

## Tags

Formato: `<FERRAMENTA> - <TIPO> - <DESCRICAO>`

| Ferramenta | Tipo | Exemplo |
| --- | --- | --- |
| GA4 | Config, Event | `GA4 - Event - purchase` |
| Google Ads | Conversion, Remarketing, Linker | `Google Ads - Conversion - Lead` |
| Floodlight | Counter, Sales | `Floodlight - Sales - Compra` |
| <outra> | | |

- Certo: `GA4 - Event - add_to_cart`
- Errado: `ga4 add to cart`, `Tag de carrinho`, `GA4_AddToCart`

## Acionadores

Formato: `<TIPO> - <CONDICAO>`

| Tipo | Prefixo | Exemplo |
| --- | --- | --- |
| Evento personalizado | `CE` | `CE - purchase` |
| Pageview | `PV` | `PV - Checkout` |
| Clique em elemento | `CLK` | `CLK - Botao Comprar` |
| Visibilidade | `VIS` | `VIS - Banner Home` |
| Envio de formulario | `FORM` | `FORM - Contato` |

## Variaveis

Formato: `<TIPO> - <FONTE>`

| Tipo | Prefixo | Exemplo |
| --- | --- | --- |
| Data Layer Variable | `DLV` | `DLV - ecommerce.transaction_id` |
| Constante | `CONST` | `CONST - GA4 Measurement ID` |
| Custom JavaScript | `CJS` | `CJS - Normaliza Email` |
| Tabela de pesquisa | `LT` | `LT - Ambiente por Hostname` |
| Cookie proprio | `COOKIE` | `COOKIE - user_id` |

## Pastas

Ver `folder_structure.md`.

## Regras gerais

1. Separador: ` - ` (espaco, hifen, espaco). Nunca `_` ou `|`.
2. Sem acento e sem caractere especial nos nomes de entidade do GTM.
3. Nome de evento GA4 aparece exatamente como esta no dataLayer, em
   `snake_case` - nao "traduza" para o portugues no nome da tag.
4. Ambiente no fim, quando houver: `GA4 - Event - purchase [STG]`.
5. Nada de numeracao sequencial (`Tag 1`, `Tag 2`) nem de nome do autor.

## Excecoes aprovadas

| Entidade | Nome fora do padrao | Motivo |
| --- | --- | --- |
| | | |
