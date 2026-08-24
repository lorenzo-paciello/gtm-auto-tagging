# GTM Auto Tagging

Agente de digital analytics que cria, organiza, lista e audita o tagueamento de
um container do Google Tag Manager, sempre guiado por uma documentacao padrao
versionada em Markdown. Construido com o [Google ADK](https://google.github.io/adk-docs/).

## Arquitetura

```
                      ┌──────────────────────┐
                      │   gtm_auto_tagger    │  agente raiz: roteia e responde
                      │  (+ skills do proj.) │  duvidas conceituais
                      └──────────┬───────────┘
              ┌──────────────────┼──────────────────┬──────────────────┐
              ▼                  ▼                  ▼                  ▼
   tags_creator_agent  container_organizer  tags_listing_agent   auditor_agent
     cria tags,          _agent               inventaria           diagnostica
     triggers,           pastas +             (read-only)          (read-only)
     variaveis           nomenclatura
              └──────────────────┴──────────────────┴──────────────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   ▼                                   ▼
            tools/ (GTM API v2)              default_docs/ + custom_docs/
```

### Sub agentes

| Agente | Escreve? | Responsabilidade |
| --- | --- | --- |
| `tags_creator_agent` | sim | cria e ajusta tags, acionadores e variaveis conforme a documentacao padrao |
| `container_organizer_agent` | sim | cria pastas, move entidades e padroniza nomenclatura |
| `tags_listing_agent` | nao | inventarios e consultas ao container |
| `auditor_agent` | nao | auditoria com severidade, cobertura de eventos e plano de acao |

O agente raiz decide para quem transferir. Em pedidos compostos ("audite e
depois organize") ele encadeia os especialistas na ordem certa.

### Documentacao padrao

`default_docs/` e a fonte da verdade que todos os agentes consultam antes de
agir: eventos GA4 (automaticos, recomendados, ecommerce), limites da
plataforma, Google Ads, Floodlight, tipos da API do GTM e convencoes de
nomenclatura, pastas e auditoria.

`custom_docs/` recebe a documentacao do proprio usuario e **tem precedencia**:
um arquivo com o mesmo caminho relativo sobrescreve o default. A skill
`default-docs-builder` conduz a criacao desses arquivos.

## Instalacao

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Credenciais

1. No Google Cloud Console, habilite a **Tag Manager API** e crie uma
   credencial OAuth 2.0 do tipo *Desktop app*.
2. Baixe o JSON para `credentials/client_secret.json`.
3. Copie `.env.example` para `.env` e preencha `GOOGLE_API_KEY`,
   `GTM_ACCOUNT_ID`, `GTM_CONTAINER_ID` e `GTM_WORKSPACE_ID`.

Os ids estao na URL do GTM:

```
tagmanager.google.com/#/container/accounts/<ACCOUNT_ID>/containers/<CONTAINER_ID>/workspaces/<WORKSPACE_ID>
```

Na primeira chamada a API, o navegador abre para o consentimento OAuth e o
token e salvo em `credentials/token.pickle`.

## Uso

```powershell
adk web        # interface de chat no navegador
adk run gtm_agent   # terminal
```

Exemplos de pedido:

- "O que tenho hoje no container?" → `tags_listing_agent`
- "Crie o evento de purchase lendo o dataLayer" → `tags_creator_agent`
- "Organize tudo em pastas por ferramenta" → `container_organizer_agent`
- "Audite meu container" → `auditor_agent`
- "Quero documentar os eventos do meu ecommerce" → skill `default-docs-builder`

## Seguranca

O projeto foi desenhado para nao causar estrago em um container de producao:

| Garantia | Como |
| --- | --- |
| Nunca publica | o escopo `tagmanager.publish` nao e solicitado |
| Nunca apaga | nao existe ferramenta de delete |
| Trabalha so no rascunho | todas as escritas vao para o workspace |
| Confirmacao antes de escrever | os prompts exigem plano aprovado pelo usuario |
| Modo de simulacao | `GTM_DRY_RUN=true` faz as ferramentas devolverem o payload sem chamar a API |
| Escrita concorrente segura | updates usam `fingerprint` (optimistic locking) |

Publicar continua sendo uma acao manual do usuario, pela interface do GTM,
depois de testar no Preview.

## Estrutura

```
gtm-auto-tagging/
├── .env                     # segredos (nao versionado)
├── .env.example
├── requirements.txt
├── credentials/             # client_secret.json + token.pickle (nao versionado)
├── default_docs/            # documentacao padrao do projeto
│   ├── ga4/                 # eventos automaticos, recomendados, ecommerce, limites
│   ├── google_ads/          # conversao, remarketing, enhanced conversions
│   ├── floodlight/          # counter, sales, variaveis uN
│   ├── gtm/                 # tipos de tag, acionador e variavel na API v2
│   └── conventions/         # nomenclatura, pastas, checklist de auditoria
├── custom_docs/             # documentacao do usuario (precedencia sobre default)
└── gtm_agent/
    ├── agent.py             # agente raiz
    ├── config.py            # settings via .env
    ├── prompts.py           # instrucoes do raiz e dos sub agentes
    ├── sub_agents/
    │   ├── tags_creator/
    │   ├── container_organizer/
    │   ├── tags_listing/
    │   └── auditor/
    ├── tools/
    │   ├── gtm_client.py    # auth, paginacao, tratamento de erro
    │   ├── gtm_read.py      # listagens e snapshot do container
    │   ├── gtm_write.py     # criacao/atualizacao de tags, triggers, variaveis
    │   ├── gtm_folders.py   # pastas e movimentacao
    │   └── docs_tools.py    # leitura e escrita da documentacao
    └── skills/
        └── default-docs-builder/   # skill de criacao da doc padrao do usuario
```

## Ferramentas disponiveis aos agentes

**Leitura** — `list_accounts`, `list_containers`, `list_workspaces`,
`list_tags`, `get_tag`, `list_triggers`, `list_variables`,
`list_built_in_variables`, `list_folders`, `get_workspace_status`,
`get_container_snapshot`

**Escrita** — `create_tag`, `update_tag`, `create_trigger`, `create_variable`,
`rename_entity`

**Organizacao** — `get_folder_map`, `list_folder_entities`, `create_folder`,
`move_entities_to_folder`

**Documentacao** — `list_docs`, `read_doc`, `search_docs`, `save_custom_doc`

As ferramentas de escrita recebem a configuracao como JSON plano
(`parameters_json`) e convertem para o formato `parameter` da API
automaticamente — texto vira `template`, inteiro vira `integer`, booleano vira
`boolean`, objeto vira `map` e lista vira `list`.

## Configuracao (.env)

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `GOOGLE_API_KEY` | — | chave do Google AI Studio |
| `GTM_ACCOUNT_ID` | — | conta padrao |
| `GTM_CONTAINER_ID` | — | container padrao |
| `GTM_WORKSPACE_ID` | `2` | workspace padrao |
| `GTM_MODEL_FAST` | `gemini-3.1-flash-lite` | modelo dos agentes de leitura |
| `GTM_MODEL_REASONING` | `gemini-3.5-flash` | modelo do raiz e dos agentes que decidem |
| `GTM_CLIENT_SECRET_FILE` | `credentials/client_secret.json` | |
| `GTM_TOKEN_FILE` | `credentials/token.pickle` | |
| `GTM_DEFAULT_DOCS_DIR` | `default_docs` | |
| `GTM_CUSTOM_DOCS_DIR` | `custom_docs` | |
| `GTM_SKILLS_DIR` | `gtm_agent/skills` | |
| `GTM_DRY_RUN` | `false` | `true` simula as escritas |

## Proximos passos sugeridos

- Suporte a container server-side (`serverPageview`, clients, transformations)
- Sub agente de versionamento (`create_version`, comparacao entre versoes)
- Exportacao do inventario para planilha ou BigQuery
- Validacao do dataLayer real via Preview/Debug antes de criar a tag
