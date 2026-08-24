# Checklist de auditoria - <NOME DO NEGOCIO>

> Versao 1.0 - atualizado em <AAAA-MM-DD> - responsavel: <NOME>

Cada item recebe: OK / Ajustar / Nao se aplica, com evidencia (id da entidade).

## 1. Cobertura

- [ ] Todos os eventos criticos do dicionario estao implementados
- [ ] Cada evento implementado tem os parametros obrigatorios documentados
- [ ] Conversoes de midia paga cobrem os mesmos eventos de negocio do GA4
- [ ] Nenhum evento importante depende exclusivamente de Custom HTML

## 2. Configuracao

- [ ] Existe uma Google Tag / configuracao GA4 unica, sem duplicidade
- [ ] Measurement ID e IDs de conversao vem de variaveis, nao hardcoded
- [ ] Tags de ecommerce leem o objeto `ecommerce` do dataLayer
- [ ] Nenhuma tag com `firingTriggerId` vazio
- [ ] Nenhuma tag pausada sem justificativa em `notes`

## 3. Consentimento e privacidade

- [ ] Consent Mode configurado, com Consent Initialization antes de tudo
- [ ] Tags de midia com `consentSettings` declarado
- [ ] Conversion Linker presente quando ha Google Ads ou Floodlight
- [ ] Nenhum dado pessoal em claro (e-mail, telefone, CPF) sendo enviado
- [ ] Enhanced Conversions usa dado com hash ou o campo `user_data` nativo

## 4. Organizacao

- [ ] Toda entidade esta em uma pasta
- [ ] Nomes seguem `naming_conventions.md`
- [ ] Sem nomes duplicados entre tags, acionadores ou variaveis
- [ ] `notes` preenchido nas entidades criticas

## 5. Higiene

- [ ] Sem acionadores orfaos
- [ ] Sem variaveis sem uso
- [ ] Sem tags de Universal Analytics ativas
- [ ] Sem Custom HTML fazendo o que uma tag nativa ja faz
- [ ] Workspace sem conflitos de merge pendentes

## 6. Publicacao

- [ ] Versoes recentes tem nome e descricao
- [ ] Ha ambiente de homologacao ou processo de Preview antes de publicar
- [ ] Alteracoes pendentes no workspace estao revisadas

## Achados

| Severidade | Entidade (id) | Problema | Recomendacao | Responsavel |
| --- | --- | --- | --- | --- |
| | | | | |
