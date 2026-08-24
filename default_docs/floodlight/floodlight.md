# Floodlight (Campaign Manager 360 / Display & Video 360)

Floodlight mede conversoes das campanhas de display e video do Google Marketing
Platform. A configuracao vem do CM360; o GTM apenas dispara a tag.

## Tipos de tag

| `type` | Nome | Uso |
| --- | --- | --- |
| `flc` | Floodlight Counter | conta acoes: pageview, lead, visita a uma secao |
| `fls` | Floodlight Sales | conta transacoes com receita e quantidade |

## Parametros

### Counter (`flc`)

| Parametro | Descricao |
| --- | --- |
| `advertiserId` | id do anunciante no CM360 (`src=`) |
| `groupTag` | Group Tag String (`cat=` no nivel de grupo, ex.: `lead`) |
| `activityTag` | Activity Tag String (`type=`, ex.: `contato0`) |
| `countingMethod` | `STANDARD` (toda vez), `UNIQUE` (uma vez por usuario/dia), `PER_SESSION` |
| `ordinalValue` | valor do `ord=`. Numero aleatorio para standard, `1` para unique |
| `enableGoogleAttributionOptions` | ativa `attributionOptionImage` |
| `customVariable` | tabela de variaveis `u1`..`u100` |

### Sales (`fls`)

| Parametro | Descricao |
| --- | --- |
| `advertiserId` | id do anunciante |
| `groupTag` / `activityTag` | idem counter |
| `orderId` | id do pedido - **deduplicacao**, vai no `ord=` |
| `revenue` | receita da transacao |
| `quantity` | quantidade de itens |
| `countingMethod` | `TRANSACTIONS` (uma linha por pedido) ou `ITEMS_SOLD` |
| `customVariable` | `u1`..`u100` |

## Variaveis customizadas (`u1`..`u100`)

Sao os parametros extras do Floodlight, mapeados no CM360. O significado de
cada `uN` e definido **na conta do CM360**, nao no GTM.

```json
{
  "advertiserId": "1234567",
  "groupTag": "compra",
  "activityTag": "trans0",
  "orderId": "{{DLV - ecommerce.transaction_id}}",
  "revenue": "{{DLV - ecommerce.value}}",
  "quantity": "{{DLV - ecommerce.total_items}}",
  "countingMethod": "TRANSACTIONS",
  "customVariable": [
    {"key": "u1", "value": "{{DLV - customer_type}}"},
    {"key": "u2", "value": "{{DLV - payment_type}}"}
  ]
}
```

Sempre peca ao usuario o **mapa de variaveis customizadas** do CM360 antes de
preencher `uN`. Enviar dado no `u` errado polui o relatorio do anunciante e e
dificil de detectar.

## Cache buster (`ord=`)

| Metodo de contagem | Valor de `ord` |
| --- | --- |
| Standard / Unique (counter) | numero aleatorio - a tag do GTM gera |
| Per session (counter) | id da sessao |
| Sales | `orderId` - garante deduplicacao |

Em `fls`, `orderId` vazio faz o CM360 contar cada refresh como uma venda nova.
Achado critico em auditoria.

## Pre-requisitos no container

1. **Conversion Linker** (`gclidw`) em todas as paginas - Floodlight depende
   dele para atribuicao em navegadores com restricao de cookie de terceiro.
2. **Consent Mode** com `ad_storage` e `ad_user_data`.
3. Se o site usa domain de mensuracao proprio, configure-o nas opcoes da tag.

## Nomenclatura

`Floodlight - Counter - <acao>` e `Floodlight - Sales - <acao>`, com o
`groupTag`/`activityTag` citados nas `notes` da tag. Sem isso, ninguem consegue
relacionar a tag do GTM com a activity do CM360.

## Checklist de auditoria

- [ ] `advertiserId` correto e consistente entre as tags
- [ ] `groupTag` e `activityTag` batem com as activities do CM360
- [ ] `fls` com `orderId` preenchido
- [ ] `countingMethod` coerente com o que a activity espera
- [ ] Conversion Linker presente
- [ ] `consentSettings` declarado
- [ ] Variaveis `uN` documentadas nas `notes`
- [ ] Sem Floodlight duplicado para a mesma activity
