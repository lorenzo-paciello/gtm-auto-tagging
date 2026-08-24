# Google Ads - conversao, remarketing e enhanced conversions

## Componentes obrigatorios

| Ordem | Tag | `type` | Papel |
| --- | --- | --- | --- |
| 1 | Consent Initialization (CMP) | `html` ou template | define o estado de consentimento antes de tudo |
| 2 | Conversion Linker | `gclidw` | grava o `gclid`/`wbraid` em cookie proprio (`_gcl_*`). **Sem ele a conversao nao e atribuida** |
| 3 | Google Tag (AW-XXXX) ou tag de conversao | `googtag` / `awct` | envia a conversao |
| 4 | Remarketing | `sp` | audiencias e remarketing dinamico |

O Conversion Linker deve disparar em **todas as paginas**, com o acionador
`Initialization - All Pages`.

## Tag de conversao (`awct`)

| Parametro | Obrigatorio | Descricao |
| --- | --- | --- |
| `conversionId` | sim | somente os digitos do `AW-XXXXXXXXX` |
| `conversionLabel` | sim | rotulo da acao de conversao |
| `conversionValue` | recomendado | valor monetario. Use variavel do dataLayer |
| `currencyCode` | se houver valor | ISO 4217 (`BRL`) |
| `orderId` | recomendado | id do pedido; e o que **deduplica** conversoes |
| `enableProductReporting` | ecommerce | ativa `merchantId`, `itemsByDataLayer` |
| `enableEnhancedConversion` | recomendado | ativa enhanced conversions |
| `userDataVariable` | com EC | variavel do tipo user-provided data |

`conversionId` e `conversionLabel` sempre em variaveis constantes, nunca
digitados na tag.

## Deduplicacao

Sem `orderId`, um refresh na pagina de obrigado conta a conversao de novo. Em
auditoria, toda tag `awct` de compra sem `orderId` e achado **critico**.

## Enhanced conversions

Enviam dados do usuario com hash para melhorar a atribuicao.

- **Nunca** monte o hash manualmente em Custom JavaScript sem necessidade: a
  tag do Google faz o SHA-256 e a normalizacao.
- Campos aceitos: `email`, `phone_number`, `address` (`first_name`,
  `last_name`, `street`, `city`, `region`, `postal_code`, `country`).
- Telefone em formato E.164 (`+5511999999999`).
- E-mail em minusculas e sem espacos.
- Requer aceite dos termos de dados do cliente no Google Ads.
- Requer base legal para o tratamento. Registre isso na documentacao do
  cliente.

Implementacao recomendada: tag "Google Analytics: user-provided data"
(`gaawllm`) ou o campo `userDataVariable` dentro da propria `awct`.

## Remarketing (`sp`)

Para remarketing dinamico, os parametros customizados precisam bater com o tipo
de negocio configurado no Google Ads:

| Vertical | Parametros |
| --- | --- |
| Varejo | `ecomm_prodid`, `ecomm_pagetype`, `ecomm_totalvalue` |
| Educacao | `dynx_itemid`, `dynx_pagetype`, `dynx_totalvalue` |
| Viagem | `dynx_itemid`, `dynx_itemid2`, `dynx_pagetype`, `dynx_totalvalue` |

Valores de `ecomm_pagetype`: `home`, `searchresults`, `category`, `product`,
`cart`, `purchase`, `other`.

## Importar conversao do GA4 em vez de usar `awct`

Alternativa valida: marcar o evento como key event no GA4 e importar no Google
Ads. Vantagens: uma unica implementacao, modelo de atribuicao do GA4.
Desvantagens: latencia maior e dependencia do vinculo entre as contas.

**Nunca use as duas ao mesmo tempo para a mesma conversao** - o Google Ads
contabiliza em dobro. Em auditoria, verifique se ha tag `awct` de compra
convivendo com conversao importada do GA4.

## Consent Mode

Tags de Google Ads devem declarar `consentSettings`:

```json
{
  "consentStatus": "NEEDED",
  "consentType": {"type": "list", "list": ["ad_storage", "ad_user_data", "ad_personalization"]}
}
```

Com Consent Mode avancado, as tags disparam mesmo sem consentimento, enviando
pings sem cookies (conversion modeling). Com o basico, elas nao disparam. A
escolha e do juridico do cliente - documente qual esta em uso.

## Checklist de auditoria

- [ ] Conversion Linker presente e disparando em todas as paginas
- [ ] Conversion Linker dispara ANTES das tags de conversao
- [ ] `conversionId` e `conversionLabel` vindos de variaveis
- [ ] `orderId` preenchido nas conversoes de compra
- [ ] `currencyCode` presente sempre que ha `conversionValue`
- [ ] Sem dupla contagem (`awct` + conversao importada do GA4)
- [ ] `consentSettings` declarado
- [ ] Nenhum dado pessoal em claro sendo enviado
