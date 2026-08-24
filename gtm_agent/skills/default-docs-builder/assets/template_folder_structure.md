# Estrutura de pastas do container - <NOME DO NEGOCIO>

> Versao 1.0 - atualizado em <AAAA-MM-DD> - responsavel: <NOME>

## Criterio escolhido

- [ ] Por **midia / ferramenta** (padrao recomendado)
- [ ] Por **funcao / jornada**
- [ ] Hibrido: <descreva>

Justificativa: <por que este criterio faz sentido para este container>

## Pastas

| Pasta | O que entra | O que NAO entra |
| --- | --- | --- |
| `GA4` | tags de evento e configuracao GA4, acionadores e variaveis exclusivos de GA4 | variaveis compartilhadas com outras midias |
| `Google Ads` | conversao, remarketing, conversion linker | |
| `Floodlight` | counter e sales | |
| `<Midia paga>` | pixels e conversoes de <ferramenta> | |
| `Consentimento` | CMP, Consent Mode, Conversion Linker | |
| `Utilitarios` | variaveis e acionadores usados por mais de uma midia | qualquer tag |
| `Depreciado` | entidades pausadas aguardando remocao | |

## Regras

1. Uma entidade pertence a uma unica pasta.
2. Entidade usada por duas ou mais midias vai para `Utilitarios`.
3. Toda tag nova nasce ja em uma pasta.
4. Pasta vazia por mais de um ciclo de revisao deve ser removida.
5. Nao criar pastas por pessoa, por data ou por projeto.

## Estado atual

| Pasta | Tags | Acionadores | Variaveis |
| --- | --- | --- | --- |
| | | | |

## Pendencias

| Item | Quem decide | Prazo |
| --- | --- | --- |
| | | |
