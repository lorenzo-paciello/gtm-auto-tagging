# GA4 - eventos automaticos e de medicao aprimorada

Eventos que o GA4 coleta sem tag adicional. **Nao crie tag para nenhum deles.**
Criar uma tag `gaawe` com `eventName: page_view` alem da Google Tag e a causa
mais comum de pageview duplicado em container GTM.

## Coletados automaticamente (web)

| Evento | Quando dispara | Parametros relevantes |
| --- | --- | --- |
| `first_visit` | primeira visita do usuario ao site | - |
| `session_start` | inicio de uma sessao | - |
| `user_engagement` | usuario ativo por >= 10s, com conversao ou >= 2 pageviews | `engagement_time_msec` |
| `page_view` | carregamento da pagina (pela Google Tag / config GA4) | `page_location`, `page_referrer`, `page_title` |

## Medicao aprimorada (Enhanced Measurement)

Habilitada na interface do GA4, em Fluxo de dados. Cada item pode ser ligado ou
desligado individualmente.

| Evento | Gatilho | Parametros |
| --- | --- | --- |
| `page_view` | carregamento e, se habilitado, mudanca de historico (SPA) | `page_location`, `page_referrer`, `page_title` |
| `scroll` | 90% de rolagem vertical, uma vez por pagina | `percent_scrolled` (sempre 90) |
| `click` | clique em link que sai do dominio | `link_classes`, `link_domain`, `link_id`, `link_url`, `outbound` |
| `view_search_results` | URL contem parametro de busca (`q`, `s`, `search`, `query`, `keyword`) | `search_term` |
| `video_start` | inicio de video YouTube incorporado com JS API ativa | `video_current_time`, `video_duration`, `video_percent`, `video_provider`, `video_title`, `video_url`, `visible` |
| `video_progress` | 10%, 25%, 50%, 75% do video | idem |
| `video_complete` | fim do video | idem |
| `file_download` | clique em link de documento, texto, executavel, apresentacao, video ou audio | `file_extension`, `file_name`, `link_classes`, `link_id`, `link_text`, `link_url` |
| `form_start` | primeira interacao com um formulario na sessao | `form_id`, `form_name`, `form_destination` |
| `form_submit` | envio do formulario | `form_id`, `form_name`, `form_destination`, `form_submit_text` |

### Decisao: medicao aprimorada ou GTM?

| Situacao | Recomendacao |
| --- | --- |
| Site institucional simples | use medicao aprimorada |
| Precisa de parametros extras no evento (ex.: categoria do formulario) | desligue o item no GA4 e implemente pelo GTM |
| SPA com roteamento complexo | desligue "Alteracoes no historico" e controle o `page_view` pelo GTM |
| Formularios em iframe ou com validacao AJAX | `form_submit` nativo nao captura; implemente pelo GTM |

Nunca deixe os dois ligados para o mesmo evento. Verifique isso em auditoria:
uma tag GTM de `form_submit` com a medicao aprimorada de formularios ativa
gera contagem dobrada.

## Coletados automaticamente (app - Firebase)

Relevantes para containers de app ou para propriedades com fluxo web + app:
`first_open`, `app_update`, `app_remove`, `app_exception`,
`app_store_subscription_*`, `in_app_purchase`, `notification_*`, `os_update`,
`screen_view`.

## Como identificar duplicidade em auditoria

1. Liste as tags `gaawe` do container.
2. Sinalize toda tag cujo `eventName` esteja na tabela acima.
3. Cheque no GA4 se o item correspondente da medicao aprimorada esta ativo.
4. Achado critico se ambos estiverem ativos.
