# Checklist de auditoria de container GTM

Lista percorrida pelo `auditor_agent`. Cada item recebe **OK / Ajustar / Nao se
aplica**, com evidencia (nome e id da entidade).

> Para adotar outro checklist, crie `custom_docs/conventions/audit_checklist.md`.

## 1. Base e ordem de carregamento

- [ ] Existe uma unica tag base do Google (`googtag` ou `gaawc`), sem duplicata
- [ ] Consent Initialization dispara antes de qualquer outra tag
- [ ] Conversion Linker (`gclidw`) presente e disparando em todas as paginas
- [ ] Nenhuma tag de midia dispara antes do consentimento
- [ ] Sem tags de Universal Analytics (`ua`) ativas

## 2. GA4

- [ ] Measurement ID vem de variavel constante, nao escrito na tag
- [ ] Nao ha tag `gaawe` duplicando evento da medicao aprimorada
      (`page_view`, `scroll`, `click`, `file_download`, `form_start`,
      `form_submit`, `video_*`, `view_search_results`)
- [ ] Nomes de evento em `snake_case`, ate 40 caracteres, sem prefixo reservado
- [ ] Eventos usam o nome recomendado pelo Google quando existe equivalente
- [ ] Nenhum evento carrega segmentacao no nome (`purchase_mobile`)
- [ ] Eventos de ecommerce leem o objeto `ecommerce` do dataLayer
- [ ] `purchase` tem `transaction_id`, `value` e `currency`
- [ ] Parametros customizados estao registrados como dimensao/metrica no GA4
- [ ] Nenhum valor de texto ultrapassa 100 caracteres

## 3. Midia paga

- [ ] `conversionId` / `conversionLabel` vindos de variaveis
- [ ] Conversoes de compra com `orderId` (deduplicacao)
- [ ] `currencyCode` presente sempre que ha valor
- [ ] Sem dupla contagem: tag `awct` convivendo com conversao importada do GA4
- [ ] Floodlight `fls` com `orderId` preenchido
- [ ] `groupTag` / `activityTag` documentados em `notes`
- [ ] Variaveis customizadas `uN` do Floodlight documentadas

## 4. Consentimento e privacidade

- [ ] `consentSettings` declarado nas tags de midia
- [ ] Modo de consentimento (basico ou avancado) identificado e documentado
- [ ] Nenhum dado pessoal em claro (e-mail, telefone, CPF) em variavel ou tag
- [ ] Enhanced Conversions usa `user_data` nativo ou hash SHA-256
- [ ] Nenhuma tag de terceiro coletando dado nao declarado na politica

## 5. Acionadores

- [ ] Nenhuma tag com `firingTriggerId` vazio
- [ ] Acionadores reutilizados entre midias, sem clones por ferramenta
- [ ] `purchase` nao dispara mais de uma vez por pedido (refresh, SPA)
- [ ] Bloqueios de ambiente de homologacao configurados
- [ ] Built-in variables necessarias habilitadas para os acionadores em uso

## 6. Variaveis

- [ ] Data Layer Variables com `dataLayerVersion: 2`
- [ ] IDs de medicao e conversao em constantes
- [ ] Variaveis `jsm` com `notes` explicando o que fazem
- [ ] Sem variaveis com nome duplicado
- [ ] Sem referencias `{{Nome}}` apontando para variavel inexistente

## 7. Organizacao

- [ ] Toda entidade em uma pasta
- [ ] Nomes seguem `conventions/naming_conventions.md`
- [ ] Sem nomes duplicados dentro de cada tipo
- [ ] `notes` preenchido nas entidades criticas
- [ ] Sem pastas com nomes proximos (`GA4` e `GA 4`)

## 8. Higiene

- [ ] Sem acionadores orfaos (nenhuma tag os referencia)
- [ ] Sem variaveis sem uso aparente (verificar as `jsm` manualmente)
- [ ] Tags pausadas tem justificativa e prazo
- [ ] Sem `html` fazendo o que uma tag nativa ou template ja faz
- [ ] Workspace sem conflito de merge pendente

## 9. Cobertura

- [ ] Todos os eventos criticos da documentacao estao implementados
- [ ] Cada evento implementado tem os parametros obrigatorios
- [ ] Conversoes de midia cobrem os mesmos eventos de negocio do GA4
- [ ] Eventos de erro e de falha de formulario existem (o funil que ninguem mede)

## Severidade

| Nivel | Criterio |
| --- | --- |
| **Critico** | dado sendo perdido, duplicado ou enviado errado; risco legal |
| **Alto** | risco de compliance ou de manutencao que ainda nao quebrou |
| **Medio** | organizacao, legibilidade, documentacao |
| **Baixo** | limpeza e higiene |

## Formato do relatorio

1. Resumo executivo (3 a 5 linhas) + nota de 0 a 10 justificada
2. Numeros do container por produto
3. Tabela: severidade | entidade (id) | problema | recomendacao
4. Cobertura de eventos: implementado x faltando
5. Plano de acao priorizado, indicando o sub agente responsavel por cada item
