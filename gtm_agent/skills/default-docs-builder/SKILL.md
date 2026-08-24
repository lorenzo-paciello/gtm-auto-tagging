---
name: default-docs-builder
description: Conduz o usuario na criacao da propria documentacao padrao de tagueamento (eventos, parametros, nomenclatura, estrutura de pastas) e grava os arquivos em custom_docs/, que tem precedencia sobre a documentacao default do projeto. Use quando o usuario quiser criar, revisar, estender ou substituir a documentacao padrao que os agentes seguem - por exemplo "quero definir meu proprio dicionario de eventos", "minha empresa usa outra nomenclatura", "documente o tagueamento do meu site".
metadata:
  adk_additional_tools:
    - save_custom_doc
    - list_docs
    - read_doc
    - search_docs
---

# Construtor de documentacao padrao

Esta skill transforma o conhecimento do usuario sobre o negocio dele em
documentacao que os sub agentes (`tags_creator_agent`,
`container_organizer_agent`, `auditor_agent`) vao seguir como fonte da verdade.

O resultado sao arquivos `.md` em `custom_docs/`. Eles **sobrepoem** os
equivalentes em `default_docs/`: se o usuario define `naming_conventions.md`
proprio, e o dele que vale.

## Antes de comecar

Rode `list_docs()` e mostre ao usuario o que ja existe. Documentacao nova deve
complementar, nao repetir. Se o usuario quiser sobrescrever um documento
default, explique que basta criar um arquivo com o **mesmo caminho relativo**
em `custom_docs/`.

## Passo 1 - Descobrir o escopo

Faca estas perguntas em UMA unica mensagem, em formato de lista. Nao interrogue
o usuario pergunta por pergunta.

1. Qual o modelo de negocio? (ecommerce, geracao de lead, midia/conteudo, SaaS,
   marketplace, app + web)
2. Quais ferramentas estao no container? (GA4, Google Ads, Floodlight/CM360,
   Meta, LinkedIn, TikTok, outras)
3. Ja existe uma convencao de nomenclatura em uso? Peca 3 a 5 exemplos reais de
   nomes de tags.
4. Quais eventos de negocio importam mais? (ex.: compra, lead, cadastro,
   assinatura de newsletter, uso de filtro, inicio de checkout)
5. Ha algo proibido ou obrigatorio? (ex.: nunca enviar e-mail em claro, sempre
   preencher `notes`, sempre respeitar Consent Mode)

Se o container ja estiver acessivel, use `search_docs` e peca ao agente raiz o
inventario atual antes de propor a nomenclatura - documentar o padrao que ja
existe custa menos que impor um novo.

## Passo 2 - Escolher os documentos a produzir

Proponha ao usuario um conjunto minimo e pergunte quais ele quer agora:

| Arquivo sugerido | Conteudo |
| --- | --- |
| `conventions/naming_conventions.md` | padrao de nome para tags, acionadores, variaveis e pastas |
| `conventions/folder_structure.md` | quais pastas existem e o que vai em cada uma |
| `ga4/events_<negocio>.md` | dicionario de eventos do negocio: nome, quando dispara, parametros |
| `ga4/data_layer.md` | contrato do dataLayer com o time de desenvolvimento |
| `conventions/audit_checklist.md` | itens que uma auditoria interna deve verificar |
| `<ferramenta>/<ferramenta>.md` | especificidades de Google Ads, Floodlight, Meta etc. |

Comece pelo dicionario de eventos: e o documento que mais muda o comportamento
dos agentes.

## Passo 3 - Escrever

Carregue o template correspondente antes de escrever:

- `load_skill_resource("default-docs-builder", "assets/template_event_dictionary.md")`
- `load_skill_resource("default-docs-builder", "assets/template_naming_conventions.md")`
- `load_skill_resource("default-docs-builder", "assets/template_folder_structure.md")`
- `load_skill_resource("default-docs-builder", "assets/template_audit_checklist.md")`

E leia as regras de qualidade em
`load_skill_resource("default-docs-builder", "references/writing_rules.md")`.

Regras nao negociaveis ao redigir:

1. **Todo evento tem uma tabela de parametros** com colunas: parametro, tipo,
   obrigatorio, origem no dataLayer, exemplo.
2. **Todo evento diz quando dispara**, em linguagem de negocio e em linguagem
   tecnica (qual evento do dataLayer, qual URL, qual seletor).
3. **Nomes de eventos GA4 seguem as regras da plataforma**: snake_case, ate 40
   caracteres, comecando por letra, sem os prefixos reservados `ga_`,
   `google_`, `firebase_` e `_`. Prefira os nomes recomendados pelo Google
   (`purchase`, `generate_lead`, `sign_up`) a nomes proprios - so crie evento
   customizado quando nao houver equivalente oficial.
4. **Nada de exemplo generico.** Use os nomes reais do negocio do usuario.
5. **Marque o que ficou em aberto** em uma secao final "Pendencias", em vez de
   inventar.

## Passo 4 - Revisar com o usuario ANTES de gravar

Mostre o Markdown completo do documento no chat e pergunte se pode gravar. Nao
chame `save_custom_doc` sem essa confirmacao explicita.

## Passo 5 - Gravar

```
save_custom_doc(doc_path="ga4/events_ecommerce.md", content="<markdown completo>")
```

- O caminho e relativo a `custom_docs/`. Subpastas sao criadas automaticamente.
- Se o arquivo ja existir, a ferramenta retorna `already_exists`. Leia o atual
  com `read_doc`, mostre a diferenca ao usuario e so entao repita a chamada com
  `overwrite=true`.
- Depois de gravar cada arquivo, confirme com `list_docs()` e mostre ao usuario
  o caminho final.

## Passo 6 - Fechar

Encerre com:

1. A lista dos arquivos criados e o que cada um governa.
2. Quais documentos default foram sobrepostos, se algum.
3. Uma sugestao de proximo passo: normalmente rodar o `auditor_agent` para
   medir o container atual contra a documentacao recem-criada.
