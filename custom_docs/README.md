# Documentacao customizada

Coloque aqui a documentacao de tagueamento do seu negocio. Arquivos deste
diretorio **sobrepoem** os equivalentes de `default_docs/` quando tem o mesmo
caminho relativo.

Exemplos:

| Arquivo | Efeito |
| --- | --- |
| `custom_docs/conventions/naming_conventions.md` | substitui o padrao de nomenclatura do projeto |
| `custom_docs/ga4/events_meu_ecommerce.md` | adiciona um dicionario de eventos proprio |
| `custom_docs/ga4/events_ecommerce.md` | substitui o funil de ecommerce padrao |

## Como criar

Peca ao agente: *"quero criar minha documentacao padrao de tagueamento"*. Ele
carrega a skill `default-docs-builder`, entrevista voce, redige em Markdown,
mostra para aprovacao e grava aqui.

Voce tambem pode escrever os arquivos a mao — sao Markdown comum. Os agentes
leem tudo que for `.md` neste diretorio, em qualquer profundidade de subpasta.
