# Regras de qualidade para documentacao de tagueamento

Uma documentacao padrao serve a tres leitores: o analista que implementa, o
desenvolvedor que precisa popular o dataLayer, e o agente que vai automatizar.
Se um dos tres nao consegue agir a partir do texto, o documento falhou.

## 1. Escreva em nivel de contrato, nao de tutorial

Errado: "O evento de compra deve ser enviado quando o usuario comprar."

Certo:

> `purchase` — dispara na pagina de confirmacao do pedido
> (`/checkout/sucesso`), pelo evento `purchase` no dataLayer, empurrado pelo
> back-end apos a confirmacao do pagamento. Nunca deve disparar no retorno do
> gateway antes da confirmacao.

## 2. Uma tabela de parametros por evento

| Parametro | Tipo | Obrigatorio | Origem | Exemplo |
| --- | --- | --- | --- | --- |
| `transaction_id` | string | sim | `dataLayer.ecommerce.transaction_id` | `PED-100294` |
| `value` | number | sim | `dataLayer.ecommerce.value` | `459.90` |
| `currency` | string | sim | constante | `BRL` |

Sem a coluna "Origem" o desenvolvedor nao sabe o que entregar, e o agente nao
sabe qual variavel criar.

## 3. Documente o dataLayer junto com o evento

Inclua o snippet exato esperado:

```javascript
dataLayer.push({ ecommerce: null });
dataLayer.push({
  event: "purchase",
  ecommerce: {
    transaction_id: "PED-100294",
    value: 459.90,
    currency: "BRL",
    items: [{ item_id: "SKU-1", item_name: "Camiseta", price: 89.90, quantity: 1 }]
  }
});
```

O `push` de `ecommerce: null` antes de cada evento de ecommerce evita que
valores do evento anterior vazem para o proximo.

## 4. Regras de nomenclatura precisam de contra-exemplos

Uma regra sem contra-exemplo e interpretada de tres formas diferentes por tres
pessoas. Sempre acompanhe a regra de um par:

- Certo: `GA4 - Event - purchase`
- Errado: `ga4 purchase`, `Tag GA4 compra`, `GA4_Event_Purchase`

## 5. Respeite os limites da plataforma GA4

- Nome de evento: ate 40 caracteres, `a-z`, `0-9` e `_`, comecando por letra.
- Ate 25 parametros por evento.
- Nome de parametro: ate 40 caracteres. Valor de texto: ate 100 caracteres
  (500 em propriedades 360).
- Ate 25 propriedades de usuario por propriedade GA4.
- Prefixos reservados: `_`, `ga_`, `google_`, `firebase_`, `gtag`.
- Nomes reservados que voce nao pode reutilizar: `first_open`, `first_visit`,
  `session_start`, `user_engagement`, `app_exception`, `in_app_purchase`,
  `screen_view`, entre outros.

Registre esses limites no documento do cliente. Eles sao a causa mais comum de
evento silenciosamente descartado.

## 6. Prefira o padrao oficial ao evento customizado

Antes de criar `compra_finalizada`, verifique se `purchase` resolve. Eventos
recomendados pelo Google alimentam relatorios prontos (Monetizacao, Geracao de
lead) e integracoes com Google Ads. Um evento customizado equivalente perde
tudo isso e ainda precisa de dimensao personalizada para ser analisado.

Documente a decisao quando fugir do padrao, com a justificativa.

## 7. Versione e date

Todo documento comeca com:

```markdown
> Versao 1.0 - atualizado em 2026-08-24 - responsavel: <nome>
```

Sem data, ninguem sabe se o documento ou o container esta certo.

## 8. Termine com "Pendencias"

Lista do que ficou indefinido, quem decide e ate quando. Documentacao honesta
sobre o que nao sabe vale mais que documentacao completa e errada.
