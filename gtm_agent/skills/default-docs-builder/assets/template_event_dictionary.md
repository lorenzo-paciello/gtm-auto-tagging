# Dicionario de eventos - <NOME DO NEGOCIO>

> Versao 1.0 - atualizado em <AAAA-MM-DD> - responsavel: <NOME>
> Plataforma: GA4 (property <G-XXXXXXX>) | Container GTM: <GTM-XXXXXXX>

## Convencao

- Nomes de evento em `snake_case`, ate 40 caracteres.
- Eventos recomendados pelo Google tem prioridade sobre eventos customizados.
- Todo evento customizado precisa de justificativa nesta pagina.

## Indice de eventos

| Evento | Categoria | Origem | Prioridade |
| --- | --- | --- | --- |
| `<evento>` | ecommerce / lead / engajamento | dataLayer / GTM auto-event | critico / alto / medio |

---

## `<nome_do_evento>`

**O que mede (negocio).** <uma frase>

**Quando dispara (tecnico).** <evento do dataLayer, URL, seletor CSS, condicao>

**Quando NAO dispara.** <casos de borda que ja causaram dado duplicado>

**Parametros**

| Parametro | Tipo | Obrigatorio | Origem | Exemplo |
| --- | --- | --- | --- | --- |
| `<param>` | string / number / boolean | sim / nao | `dataLayer.<caminho>` | `<exemplo>` |

**Dimensoes e metricas personalizadas necessarias no GA4**

| Parametro | Escopo | Nome do relatorio |
| --- | --- | --- |
| `<param>` | evento / usuario | `<nome>` |

**Snippet do dataLayer**

```javascript
dataLayer.push({
  event: "<nome_do_evento>",
  // ...
});
```

**Destinos**

| Ferramenta | Acao |
| --- | --- |
| GA4 | evento `<nome>` |
| Google Ads | conversao `<nome>` (`AW-XXXX/<label>`) |
| Floodlight | activity `<tag string>` |

**Notas de implementacao.** <particularidades, riscos, dependencias>

---

## Pendencias

| Item | Quem decide | Prazo |
| --- | --- | --- |
| | | |
