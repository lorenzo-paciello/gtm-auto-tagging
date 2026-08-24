# GTM - tipos de variavel na API v2

| `type` | Nome na interface | Parametros |
| --- | --- | --- |
| `v` | Variavel da camada de dados | `name` (caminho, ex.: `ecommerce.value`), `dataLayerVersion` (use `2`), `setDefaultValue`, `defaultValue` |
| `c` | Constante | `value` |
| `jsm` | JavaScript personalizado | `javascript` (funcao anonima que retorna um valor) |
| `j` | Variavel JavaScript | `name` (variavel global, ex.: `document.title`) |
| `u` | URL | `component` (`URL`, `HOST`, `PATH`, `QUERY`, `FRAGMENT`, `PROTOCOL`), `queryKey` |
| `f` | Referenciador HTTP | `component` |
| `k` | Cookie proprio | `name`, `decodeCookie` |
| `d` | Elemento DOM | `elementId` ou `elementSelector`, `attributeName` |
| `e` | Evento personalizado | sem parametros; devolve o nome do evento |
| `smm` | Tabela de pesquisa | `input`, `map` (lista de pares), `defaultValue` |
| `remm` | Tabela de expressoes regulares | `input`, `map`, `fullMatch`, `ignoreCase` |
| `aev` | Variavel de evento automatico | `varType` (`ELEMENT`, `CLASSES`, `ID`, `TARGET`, `TEXT`, `URL`, `ATTRIBUTE`) |
| `r` | Numero aleatorio | |
| `ctv` | Numero da versao do container | |
| `dbg` | Modo de depuracao | |
| `gtes` | Configuracoes de evento do Google Tag | `eventSettingsTable` |
| `gtcs` | Configuracoes do Google Tag | `configSettingsTable` |
| `vis` | Percentual visivel / built-in de visibilidade | |

## Exemplos de `parameters_json`

### Data Layer Variable

```json
{"name": "ecommerce.transaction_id", "dataLayerVersion": 2}
```

Com valor padrao:

```json
{"name": "user_id", "dataLayerVersion": 2, "setDefaultValue": true, "defaultValue": "(nao logado)"}
```

### Constante

```json
{"value": "G-XXXXXXXXXX"}
```

### URL - parametro de query

```json
{"component": "QUERY", "queryKey": "utm_source"}
```

### Tabela de pesquisa (ambiente por hostname)

```json
{
  "input": "{{Page Hostname}}",
  "defaultValue": "producao",
  "map": [
    {"key": "staging.exemplo.com.br", "value": "homologacao"},
    {"key": "localhost", "value": "desenvolvimento"}
  ]
}
```

> A tabela de pesquisa na API usa uma lista de mapas com as chaves `key` e
> `value`. A ferramenta converte o JSON plano automaticamente.

### JavaScript personalizado

```json
{"javascript": "function() {\n  return document.title.trim().toLowerCase();\n}"}
```

## Regras do projeto

1. **Todo ID de medicao, conversao ou advertiser vira uma constante.** Trocar
   de propriedade nao pode exigir editar dez tags.
2. **Data Layer Variable sempre com `dataLayerVersion: 2`.** A versao 1 nao
   entende caminhos com ponto (`ecommerce.value`).
3. **`jsm` e o ultimo recurso.** Custom JavaScript nao e auditavel por quem nao
   le codigo e e a origem mais comum de variavel "fantasma" em auditoria.
   Toda variavel `jsm` precisa de `notes` explicando o que faz.
4. **Nunca coloque dado pessoal em claro em uma variavel** que va para midia.
   Para Enhanced Conversions, use o campo `user_data` nativo ou hash SHA-256.
5. **Renomear variavel nao atualiza as referencias.** `{{Nome antigo}}` dentro
   das tags continua apontando para um nome que nao existe mais, e a tag passa
   a enviar string vazia. Antes de renomear, liste todos os usos.

## Variaveis integradas recomendadas

Habilite pelo menos: Page URL, Page Hostname, Page Path, Referrer, Event,
Click Element, Click Classes, Click ID, Click Text, Click URL, Form Element,
Form ID, Form Classes, Scroll Depth Threshold, Container ID, Debug Mode.
