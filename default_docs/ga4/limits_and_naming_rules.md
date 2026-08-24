# GA4 - limites, nomes reservados e regras de nomenclatura

Regras da plataforma. Violar qualquer uma delas faz o GA4 descartar o evento ou
o parametro **silenciosamente** - sem erro no Preview, sem alerta na interface.

## Nomes de evento

| Regra | Valor |
| --- | --- |
| Caracteres permitidos | letras, numeros e `_` |
| Primeiro caractere | precisa ser uma letra |
| Tamanho maximo | 40 caracteres |
| Case | diferencia maiusculas de minusculas - `Purchase` != `purchase`. Use sempre minusculas |
| Espacos | nao permitidos |
| Eventos distintos por propriedade | 500 |

## Parametros

| Regra | Valor |
| --- | --- |
| Parametros por evento | ate 25 (alem dos automaticos) |
| Tamanho do nome | 40 caracteres |
| Tamanho do valor (texto) | 100 caracteres (500 em propriedades 360) |
| Dimensoes personalizadas de escopo evento | 50 (125 em 360) |
| Metricas personalizadas | 50 (125 em 360) |
| Dimensoes de escopo item | 10 (25 em 360) |

Todo parametro customizado precisa ser registrado como **dimensao ou metrica
personalizada** no GA4 para aparecer em relatorio. Parametro enviado e nao
registrado fica acessivel apenas em BigQuery e no relatorio em tempo real.

## Propriedades de usuario

| Regra | Valor |
| --- | --- |
| Propriedades por propriedade GA4 | 25 |
| Tamanho do nome | 24 caracteres |
| Tamanho do valor | 36 caracteres |

## Prefixos reservados

Nunca use como prefixo de evento, parametro ou propriedade de usuario:

- `_` (underscore)
- `ga_`
- `google_`
- `firebase_`
- `gtag`

## Nomes de evento reservados

Nao podem ser reutilizados para eventos customizados:

`ad_activeview`, `ad_click`, `ad_exposure`, `ad_impression`, `ad_query`,
`ad_reward`, `adunit_exposure`, `app_background`, `app_clear_data`,
`app_exception`, `app_install`, `app_remove`, `app_store_refund`,
`app_store_subscription_cancel`, `app_store_subscription_convert`,
`app_store_subscription_renew`, `app_update`, `app_upgrade`,
`dynamic_link_app_open`, `dynamic_link_app_update`,
`dynamic_link_first_open`, `error`, `firebase_campaign`,
`firebase_in_app_message_action`, `firebase_in_app_message_dismiss`,
`firebase_in_app_message_impression`, `first_open`, `first_visit`,
`in_app_purchase`, `notification_dismiss`, `notification_foreground`,
`notification_open`, `notification_receive`, `os_update`, `screen_view`,
`session_start`, `user_engagement`.

## Nomes de parametro reservados

`firebase_conversion`, `engagement_time_msec`, `session_id`,
`ga_session_id`, `ga_session_number`, `page_title`, `page_location`,
`page_referrer` (estes tres ultimos podem ser sobrescritos deliberadamente na
tag, mas nunca usados para outro significado).

## Boas praticas de nomenclatura de evento

1. **Verbo no infinitivo/passado + objeto**, em ingles e `snake_case`:
   `add_to_cart`, `generate_lead`, `view_item`.
2. **Nunca coloque a dimensao no nome do evento.** Errado:
   `purchase_mobile`, `purchase_desktop`. Certo: `purchase` com parametro
   `device_category`. Cada variante no nome consome uma das 500 vagas de evento
   e impede somar o total.
3. **Nao traduza.** `compra` quebra os relatorios prontos de Monetizacao e a
   importacao de conversao no Google Ads.
4. **Reuse o evento recomendado** antes de criar um customizado. Ver
   `ga4/events_recommended.md`.

## Checagem rapida antes de criar um evento

- [ ] Existe evento automatico ou recomendado equivalente?
- [ ] O nome respeita 40 caracteres, `snake_case`, sem prefixo reservado?
- [ ] Os parametros customizados serao registrados como dimensao/metrica?
- [ ] O valor de texto cabe em 100 caracteres?
- [ ] O evento representa uma acao, nao uma segmentacao?
