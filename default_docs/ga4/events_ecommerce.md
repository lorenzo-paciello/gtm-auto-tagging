# GA4 - ecommerce

Funil oficial. Os relatorios de Monetizacao dependem destes nomes exatos e do
array `items`.

## Funil e ordem de disparo

| # | Evento | Quando | Parametros de evento |
| --- | --- | --- | --- |
| 1 | `view_item_list` | lista/vitrine de produtos exibida | `item_list_id`, `item_list_name`, `items` |
| 2 | `select_item` | clique em um produto da lista | `item_list_id`, `item_list_name`, `items` |
| 3 | `view_item` | pagina de detalhe do produto | `currency`, `value`, `items` |
| 4 | `add_to_wishlist` | adiciona a lista de desejos | `currency`, `value`, `items` |
| 5 | `add_to_cart` | adiciona ao carrinho | `currency`, `value`, `items` |
| 6 | `view_cart` | visualiza o carrinho | `currency`, `value`, `items` |
| 7 | `remove_from_cart` | remove do carrinho | `currency`, `value`, `items` |
| 8 | `begin_checkout` | inicia o checkout | `currency`, `value`, `coupon`, `items` |
| 9 | `add_shipping_info` | escolhe o frete | `currency`, `value`, `coupon`, `shipping_tier`, `items` |
| 10 | `add_payment_info` | escolhe o pagamento | `currency`, `value`, `coupon`, `payment_type`, `items` |
| 11 | `purchase` | pedido confirmado | `transaction_id`, `value`, `currency`, `tax`, `shipping`, `coupon`, `items` |
| 12 | `refund` | reembolso total ou parcial | `transaction_id`, `value`, `currency`, `items` (parcial) |

Complementares: `view_promotion` e `select_promotion`, com `promotion_id`,
`promotion_name`, `creative_name`, `creative_slot`.

## Array `items`

| Campo | Tipo | Obrigatorio | Observacao |
| --- | --- | --- | --- |
| `item_id` | string | sim* | SKU. *Obrigatorio se `item_name` ausente |
| `item_name` | string | sim* | *Obrigatorio se `item_id` ausente |
| `affiliation` | string | nao | loja ou seller |
| `coupon` | string | nao | cupom no nivel do item |
| `discount` | number | nao | desconto unitario, em moeda |
| `index` | number | nao | posicao do item na lista (base 1) |
| `item_brand` | string | nao | |
| `item_category` a `item_category5` | string | nao | hierarquia da categoria |
| `item_list_id` / `item_list_name` | string | nao | lista de origem |
| `item_variant` | string | nao | cor, tamanho |
| `location_id` | string | nao | Google Place ID |
| `price` | number | nao | preco unitario, sem simbolo de moeda |
| `quantity` | number | nao | padrao 1 |

Limite: **200 itens** por evento. `price` e `value` sao numeros, nunca string
formatada (`"R$ 459,90"` quebra a coleta).

## Coerencia de `value`

`value` deve ser a soma de `price * quantity` dos itens. Divergencia entre
`value` e o array `items` e achado critico em auditoria - o GA4 usa `value`
para receita e `items` para os relatorios de produto, e eles ficam
inconsistentes.

Em `purchase`, `value` normalmente **inclui** frete e impostos apenas se essa
for a definicao de receita do negocio; `tax` e `shipping` sao enviados a parte.
Documente a escolha em `custom_docs/`.

## dataLayer

Sempre limpe o objeto `ecommerce` antes de cada evento, para nao vazar valores
do evento anterior:

```javascript
dataLayer.push({ ecommerce: null });
dataLayer.push({
  event: "purchase",
  ecommerce: {
    transaction_id: "PED-100294",
    value: 459.90,
    tax: 12.50,
    shipping: 19.90,
    currency: "BRL",
    coupon: "PRIMEIRACOMPRA",
    items: [
      {
        item_id: "SKU-1",
        item_name: "Camiseta basica",
        item_brand: "Marca",
        item_category: "Vestuario",
        item_variant: "Preta / M",
        price: 89.90,
        quantity: 2,
        index: 1
      }
    ]
  }
});
```

## Implementacao no GTM

1. **Variavel** `DLV - ecommerce` (Data Layer Variable, versao 2), apontando
   para `ecommerce`.
2. **Acionador** de evento personalizado por evento (`CE - purchase`).
3. **Tag** GA4 Event (`gaawe`) com `eventName` igual ao evento e a opcao
   "Enviar dados de ecommerce" lendo o Data Layer.
4. Parametros como `transaction_id` e `value` sao lidos do objeto `ecommerce`
   automaticamente quando essa opcao esta ativa - nao os repita manualmente na
   tabela de parametros do evento.

## Prevencao de compra duplicada

`purchase` disparando mais de uma vez por pedido e o erro mais caro do
ecommerce. Verifique em auditoria:

- [ ] O acionador tem "uma vez por evento", nao "uma vez por pagina"?
- [ ] A pagina de sucesso e acessivel por refresh (F5)?
- [ ] O `transaction_id` esta sempre presente? Sem ele o GA4 nao deduplica.
- [ ] Em SPA, o evento nao dispara de novo na navegacao de volta?
