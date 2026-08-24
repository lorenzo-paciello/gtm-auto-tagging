# GTM - tipos de tag na API v2

O campo `type` no corpo de uma tag usa um codigo curto, diferente do nome que
aparece na interface. Use esta tabela ao chamar `create_tag` e ao traduzir um
inventario para o usuario.

## Google

| `type` | Nome na interface | Parametros principais |
| --- | --- | --- |
| `googtag` | Google Tag | `tagId` (G-XXXX, AW-XXXX ou GT-XXXX), `configSettingsTable`, `eventSettingsTable` |
| `gaawe` | Evento do Google Analytics (GA4) | `eventName`, `measurementId` ou `measurementIdOverride`, `eventSettingsTable`, `userProperties`, `sendEcommerceData`, `getEcommerceDataFrom` |
| `gaawc` | Configuracao do GA4 (legado, substituida por `googtag`) | `measurementId`, `fieldsToSet` |
| `awct` | Acompanhamento de conversoes do Google Ads | `conversionId`, `conversionLabel`, `orderId`, `conversionValue`, `currencyCode`, `enableProductReporting`, `enableEnhancedConversion` |
| `sp` | Remarketing do Google Ads | `conversionId`, `customParams`, `enableDynamicRemarketing` |
| `gclidw` | Conversion Linker | `enableCrossDomain`, `acceptIncoming`, `linkerDomains`, `cookiePrefix` |
| `flc` | Floodlight Counter | `advertiserId`, `groupTag`, `activityTag`, `countingMethod`, `ordinalValue`, `enableGoogleAttributionOptions` |
| `fls` | Floodlight Sales | `advertiserId`, `groupTag`, `activityTag`, `orderId`, `revenue`, `quantity` |
| `gaawllm` | Google Analytics: user-provided data | `userDataSource`, campos de e-mail/telefone/endereco |
| `ua` | Universal Analytics (descontinuado) | achado critico em auditoria: nao coleta mais dado |

## Genericas

| `type` | Nome na interface | Uso |
| --- | --- | --- |
| `html` | HTML personalizado | `html`, `supportDocumentWrite`. Ultimo recurso |
| `img` | Pixel de imagem personalizado | `url`, `cacheBusterQueryParam`, `useCacheBuster` |
| `cvt_<containerId>_<templateId>` | Template da comunidade | parametros definidos pelo template |
| `zone` | Zona (container 360) | |

## Terceiros comuns

Pixels de Meta, LinkedIn, TikTok e similares aparecem quase sempre como
templates da galeria (`cvt_*`) ou como `html`. Ao inventariar, identifique pelo
nome da tag e pelo conteudo dos parametros, nao pelo `type`.

## Como montar `parameters_json`

A ferramenta `create_tag` recebe um JSON plano e converte para o formato
`parameter` da API. Regras de conversao:

| Valor Python/JSON | Tipo na API |
| --- | --- |
| texto | `template` |
| numero inteiro | `integer` |
| `true` / `false` | `boolean` |
| objeto `{}` | `map` |
| lista `[]` | `list` |

Referencias a variaveis do GTM usam `{{Nome da variavel}}` dentro do texto.

### Exemplo - evento GA4 com parametros

```json
{
  "eventName": "generate_lead",
  "measurementIdOverride": "{{CONST - GA4 Measurement ID}}",
  "eventSettingsTable": [
    {"parameter": "form_name", "parameterValue": "{{DLV - form_name}}"},
    {"parameter": "value", "parameterValue": "{{DLV - lead_value}}"},
    {"parameter": "currency", "parameterValue": "BRL"}
  ]
}
```

### Exemplo - ecommerce lendo o dataLayer

```json
{
  "eventName": "purchase",
  "measurementIdOverride": "{{CONST - GA4 Measurement ID}}",
  "sendEcommerceData": true,
  "getEcommerceDataFrom": "dataLayer"
}
```

### Exemplo - conversao do Google Ads

```json
{
  "conversionId": "{{CONST - Google Ads Conversion ID}}",
  "conversionLabel": "AbC-D_efG-h12_34-567",
  "orderId": "{{DLV - ecommerce.transaction_id}}",
  "conversionValue": "{{DLV - ecommerce.value}}",
  "currencyCode": "BRL"
}
```

### Exemplo - Floodlight Sales

```json
{
  "advertiserId": "1234567",
  "groupTag": "compra",
  "activityTag": "trans0",
  "orderId": "{{DLV - ecommerce.transaction_id}}",
  "revenue": "{{DLV - ecommerce.value}}",
  "countingMethod": "TRANSACTIONS"
}
```

## Regras do projeto

1. `html` so quando nao existir tag nativa nem template da galeria. Toda tag
   `html` precisa de justificativa em `notes`.
2. IDs de medicao e de conversao ficam em variaveis constantes, nunca
   escritos direto na tag - senao trocar de ambiente vira uma caçada.
3. Toda tag de midia paga declara `consentSettings`.
4. Configure `Consent Initialization` e `Conversion Linker` antes de qualquer
   tag de conversao.
