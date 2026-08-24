# GTM - tipos de acionador na API v2

| `type` | Nome na interface | Observacao |
| --- | --- | --- |
| `pageview` | Visualizacao de pagina | dispara no inicio do carregamento |
| `domReady` | DOM pronto | |
| `windowLoaded` | Janela carregada | |
| `init` | Inicializacao | antes de qualquer pageview |
| `consentInit` | Inicializacao de consentimento | primeiro de todos; use para a CMP |
| `customEvent` | Evento personalizado | le `event` do dataLayer |
| `click` | Clique - todos os elementos | exige built-in variables de clique |
| `linkClick` | Clique - apenas links | tem `waitForTags` e `checkValidation` |
| `formSubmission` | Envio de formulario | idem |
| `elementVisibility` | Visibilidade do elemento | `selectorType`, `elementId`/`elementSelector`, `firingFrequency` |
| `scrollDepth` | Profundidade de rolagem | `verticalThresholdUnits`, `verticalThresholdsPercent` |
| `timer` | Cronometro | `interval`, `limit` |
| `historyChange` | Alteracao no historico | SPA |
| `jsError` | Erro de JavaScript | |
| `youTubeVideo` | Video do YouTube | `captureStart`, `captureComplete`, `captureProgress`, `progressThresholdsPercent` |
| `triggerGroup` | Grupo de acionadores | `triggerIds` |
| `always` | Todas as paginas (sem condicao) | |
| `serverPageview` | Solicitacao do cliente (container server-side) | |

## Filtros

Um acionador tem duas listas de condicao:

- `customEventFilter` - apenas para `customEvent`: compara `{{_event}}` com o
  nome do evento.
- `filter` - condicoes adicionais ("dispara quando..."), aplicadas a qualquer
  tipo.

A ferramenta `create_trigger` monta as duas para voce:

```
create_trigger(
  name="CE - purchase",
  trigger_type="customEvent",
  custom_event_name="purchase",
  filters_json='[{"variable": "Page Path", "operator": "contains", "value": "/checkout/sucesso"}]'
)
```

### Operadores validos

| Operador | Significado |
| --- | --- |
| `equals` | igual |
| `contains` | contem |
| `startsWith` | comeca com |
| `endsWith` | termina com |
| `matchRegex` | corresponde a regex |
| `matchCssSelector` | corresponde ao seletor CSS |
| `urlMatches` | corresponde a URL |
| `greater`, `greaterOrEquals` | maior, maior ou igual |
| `less`, `lessOrEquals` | menor, menor ou igual |

Cada operador tem a versao negada com o prefixo `_not` no comportamento da
interface ("nao contem"); na API isso e representado pelo campo `negate` do
filtro.

## Padroes do projeto

1. **Prefira `customEvent`** a acionadores automaticos sempre que o dado vier
   do dataLayer. Acionador de clique baseado em texto ou classe CSS quebra na
   primeira mudanca de layout.
2. **Um acionador por evento de negocio**, reutilizado por todas as tags que
   precisam dele (GA4, Google Ads, Floodlight, Meta). Nao crie
   `CE - purchase (GA4)` e `CE - purchase (Ads)`.
3. **`elementVisibility`** para banners e secoes; defina `firingFrequency` como
   "uma vez por pagina" salvo requisito contrario.
4. **Bloqueio**: use `blockingTriggerId` em vez de criar excecoes dentro do
   nome da tag. Ex.: um acionador `EXC - Ambiente de homologacao` que bloqueia
   tags de midia quando o hostname e de staging.
5. Nomeie seguindo `conventions/naming_conventions.md`
   (`CE - purchase`, `PV - Checkout`, `CLK - Botao Comprar`).

## Variaveis integradas necessarias

Alguns acionadores nao funcionam sem as built-in variables habilitadas. Cheque
com `list_built_in_variables`:

| Acionador | Variaveis necessarias |
| --- | --- |
| `click`, `linkClick` | Click Element, Click Classes, Click ID, Click Text, Click URL |
| `formSubmission` | Form Element, Form Classes, Form ID, Form Target, Form URL, Form Text |
| `elementVisibility` | Percent Visible, On-Screen Duration |
| `scrollDepth` | Scroll Depth Threshold, Scroll Depth Units, Scroll Direction |
| `youTubeVideo` | Video Provider, Video Status, Video Title, Video Percent |
| `historyChange` | History Source, New History Fragment, Old History Fragment |
