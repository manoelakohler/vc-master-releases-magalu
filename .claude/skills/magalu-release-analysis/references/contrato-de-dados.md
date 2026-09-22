# Contrato de dados

Este é o contrato entre a skill e o código Python do repositório. O código produz estas
estruturas; a planilha e a auditoria as consomem. Divergência entre o código e este arquivo
é defeito do código.

---

## Registro de fato

A unidade atômica da análise. Um valor extraído de um documento, com tudo o que torna esse
valor verificável.

| Campo | Tipo | Regra |
|---|---|---|
| `fato_id` | string | identificador único e estável dentro da execução |
| `metrica_id` | enum | do catálogo, ou id novo documentado |
| `metrica_rotulo` | string | **rótulo literal usado no documento** |
| `segmento` | enum | ver vocabulários |
| `base` | enum | `reportado` / `ajustado` / `indefinido` |
| `periodicidade` | enum | `trimestre` / `acumulado` / `anual` |
| `tipo_valor` | enum | ver vocabulários |
| `periodo_fiscal` | string | canônico ordenável (`2025-Q2`) |
| `periodo_rotulo` | string | como o documento escreveu (`2T25`) |
| `valor_original` | string | **literal, sem limpeza** |
| `valor_normalizado` | float \| null | `null` se a unidade for ambígua |
| `unidade` | string \| null | `null` quando não determinável |
| `documento_id` | string | referência à aba Documentos |
| `pagina` | int | página do PDF onde o valor está |
| `trecho_fonte` | string | trecho literal que contém o valor |
| `confianca` | enum | `alta` / `media` / `baixa` |
| `flags` | lista | gatilhos disparados (ver `revisao-e-auditoria.md`) |
| `revisao_humana` | bool | verdadeiro se qualquer gatilho disparou |
| `motivo` | string \| null | por que precisa de revisão, ou por que está `null` |

### Invariantes

Estas condições valem para todo registro. A auditoria as verifica.

- `valor_original` **nunca** é nulo. Se não há texto de origem, não há fato — não crie o
  registro.
- `valor_normalizado = null` ⟺ (`unidade = null`) ou marcador de ausência ou gatilho de
  unidade ambígua. A relação é verificável e a auditoria a checa.
- `valor_normalizado` nunca é `0` para representar ausência.
- `documento_id`, `pagina` e `trecho_fonte` são obrigatórios. Um fato sem os três não é
  fato — é suposição.
- `trecho_fonte` precisa **conter** `valor_original`. Se não contém, a evidência não sustenta
  o valor: `confianca = baixa` no mínimo, e provavelmente pendência.
- `revisao_humana = true` ⟺ `flags` não vazio.
- `confianca = baixa` implica `revisao_humana = true`.

---

## Vocabulários controlados

Valores fora destas listas são erro, não extensão informal.

**`segmento`**
`consolidado` · `lojas_fisicas` · `ecommerce` · `marketplace` · `1p` · `3p` · `servicos` ·
`outro`

`marketplace` e `3p` coexistem porque nem todo release os usa como sinônimo; preserve o que
o documento disse. `outro` exige `motivo` preenchido.

**`base`**
`reportado` · `ajustado` · `indefinido`

`indefinido` não é um valor confortável de deixar — ele existe justamente para não forçar
uma escolha. Sempre acompanha pendência.

**`periodicidade`**
`trimestre` · `acumulado` · `anual`

**`tipo_valor`**
`absoluto` · `percentual` · `variacao_abs` · `variacao_pct` · `variacao_pp` · `texto`

`percentual` é um nível (margem de 28,4%). `variacao_pp` é uma diferença entre níveis
(+2,3 p.p.). Não são intercambiáveis.

**`confianca`**
`alta` — valor em tabela bem estruturada, cabeçalho de período e unidade inequívocos.
`media` — valor claro, mas com algum elemento de contexto inferido do entorno.
`baixa` — qualquer dúvida sobre período, unidade, base, segmento ou integridade do trecho.

Variação não é calculada quando qualquer ponta é `baixa`.

---

## Série

Agrupa fatos comparáveis. **A identidade da série é a tupla completa:**

```
(metrica_id, segmento, base, periodicidade, tipo_valor)
```

Se dois fatos não compartilham a tupla inteira, **não pertencem à mesma série e não se
comparam**. Essa é a regra que impede lucro ajustado de virar lucro reportado, trimestre de
virar acumulado e e-commerce de virar consolidado — cada uma dessas misturas produz uma
série que parece coerente e conta uma história falsa.

| Campo | Tipo | Regra |
|---|---|---|
| `serie_id` | string | derivado da tupla |
| `metrica_id`, `segmento`, `base`, `periodicidade`, `tipo_valor` | enum | a tupla |
| `unidade_serie` | string \| null | escala única normalizada da série |
| `pontos` | lista | **exatamente `N` posições**, ordem cronológica crescente |
| `confianca_minima` | enum | a pior confiança entre os pontos presentes |
| `revisao_humana` | bool | verdadeiro se qualquer ponto exigir revisão |

Cada ponto: `periodo_fiscal`, `fato_id` (ou `null`), `valor_normalizado` (ou `null`),
`valor_original` (ou `null`).

**A série tem sempre `N` posições**, uma por período analisado, em ordem crescente. Período
sem fato é uma posição com `null` — a lista não encolhe e os valores não deslizam para
preencher lacunas.

---

## Variação

Calculada entre pontos consecutivos **da mesma série**, nunca entre séries.

| Campo | Tipo | Regra |
|---|---|---|
| `serie_id` | string | série de origem |
| `periodo_de`, `periodo_para` | string | canônicos |
| `base_comparacao` | enum | `periodo_anterior` / `mesmo_trimestre_ano_anterior` |
| `variacao_abs` | float \| null | monetários e quantidades |
| `variacao_pct` | float \| null | monetários e quantidades |
| `variacao_pp` | float \| null | apenas para `percentual` |
| `calculada` | bool | falso quando suprimida |
| `motivo_nao_calculada` | string \| null | obrigatório quando `calculada = false` |

**Quando não calcular** — e o resultado é `null` com motivo, nunca `0`, nunca infinito:

- valor anterior igual a zero → `variacao_pct` não existe
- qualquer ponta ausente (`null`)
- qualquer ponta com `confianca = baixa`
- `tipo_valor = texto` → comparação apenas qualitativa
- `tipo_valor = percentual` → usa `variacao_pp`, nunca `variacao_pct`

`base_comparacao` é obrigatória e aparece na planilha. "Cresceu 12%" significa coisas
diferentes contra o trimestre anterior e contra o mesmo trimestre do ano anterior, e o
leitor não tem como adivinhar qual está vendo.

---

## Documento

| Campo | Regra |
|---|---|
| `documento_id` | único e estável |
| `titulo` | como publicado |
| `tipo` | `release_resultados` / `nao_classificado` |
| `periodo_fiscal`, `periodo_rotulo` | do conteúdo, não do nome do arquivo |
| `url_origem` | URL oficial de onde veio |
| `data_publicacao` | conforme a fonte, ou `null` |
| `arquivo_local`, `bytes`, `sha256` | rastreabilidade do arquivo exato |
| `paginas` | contagem |
| `textual` | bool — falso ⇒ não processado, pendência aberta |
| `baixado_em` | data/hora do download |

Só documentos com `tipo = release_resultados` entram na análise. `nao_classificado` é
registrado e vira pendência — nunca é incluído por eliminação.

---

## Pendência

| Campo | Regra |
|---|---|
| `pendencia_id` | único |
| `tipo` | um dos dez gatilhos de `revisao-e-auditoria.md` |
| `severidade` | `alta` / `media` / `baixa` |
| `descricao` | o que foi observado, em linguagem verificável |
| `referencias` | `fato_id` / `documento_id` / `serie_id` envolvidos |
| `valores_conflitantes` | lista, quando houver conflito — **todos os lados preservados** |
| `acao_sugerida` | o que um humano deve conferir |
| `status` | `aberta` (padrão) |

Pendência não é log. É saída de primeira classe: aparece na planilha, é contada na auditoria
e é mencionada no resumo.

---

## Verificação de auditoria

| Campo | Regra |
|---|---|
| `check_id` | identificador estável da verificação |
| `descricao` | o que foi verificado |
| `esperado`, `obtido` | valores comparados |
| `resultado` | `PASS` / `FAIL` / `ALERTA` |
| `severidade` | `alta` / `media` / `baixa` |
| `detalhe` | referências suficientes para investigar |

Toda execução grava o conjunto completo de verificações, inclusive as que passaram — é isso
que permite provar que a auditoria rodou.
