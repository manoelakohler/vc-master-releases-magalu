# Revisão humana e auditoria

Dois momentos distintos. A **revisão humana** é acionada durante a extração e a redação,
item a item. A **auditoria** roda no fim, sobre o conjunto, antes de qualquer alegação de
conclusão.

---

## Parte 1 — Gatilhos de revisão humana

O princípio: **marcar é sempre permitido; adivinhar nunca é.** Uma pendência bem descrita é
entrega válida e útil. Um número inventado é defeito, e um defeito que ninguém percebe.

Quando um gatilho dispara, o registro recebe a flag, `revisao_humana = true`, e uma linha
na aba Pendências. O valor **não** é descartado — ele fica com a marca. Descartar o valor
esconde a dúvida; marcá-lo entrega a dúvida a quem pode resolvê-la.

### Os dez gatilhos

**1. Confiança baixa**
*Sintoma:* o `trecho_fonte` não contém o valor de forma isolada e inequívoca; o número foi
reconstruído a partir de fragmentos; período ou unidade vieram de inferência de contexto.
*Ação:* `confianca = baixa`, pendência aberta, e **nenhuma variação é calculada** a partir
desse ponto. A variação herdaria a fragilidade e a esconderia atrás de um número redondo.

**2. Conflito**
*Sintoma:* o mesmo `(métrica, segmento, base, periodicidade, período)` aparece com valores
diferentes em documentos distintos do conjunto — tipicamente reapresentação, quando o release
mais novo revisa um período do mais antigo.
*Ação:* registre **todos os lados**, cada um com sua evidência, em `valores_conflitantes`.
Não escolha, não sobrescreva, não "use o mais recente". A divergência costuma ser o achado
mais relevante da análise.

**3. Ambiguidade**
*Sintoma:* dois ou mais candidatos plausíveis para a mesma métrica na mesma página, sem
critério objetivo no documento para separá-los.
*Ação:* registre os candidatos com suas evidências e descreva por que são indistinguíveis.

**4. Unidade não clara**
*Sintoma:* cabeçalho de unidade ausente, distante, perdido na extração, ou conflitante entre
tabela e narrativa.
*Ação:* `valor_normalizado = null`, `unidade = null`, `valor_original` preservado. Um número
certo em unidade errada é muito pior que um número ausente.

**5. Tabela sem estrutura**
*Sintoma:* colunas fundidas, números concatenados, células deslocadas, cabeçalho separado do
corpo na extração de texto.
*Ação:* **não extraia dessa tabela.** Não tente reconstruir o alinhamento por proximidade —
um número na linha errada é indetectável depois. Registre a página como pendência.

**6. Dúvida entre ajustado e reportado**
*Sintoma:* rótulo curto ("EBITDA", "lucro líquido") numa página que apresenta as duas
versões; ajuste mencionado em rodapé sem indicar a quais linhas se aplica.
*Ação:* `base = indefinido` e pendência. Não presuma que o nome curto significa reportado.

**7. Dúvida entre trimestre e acumulado**
*Sintoma:* coluna sem cabeçalho de período; release de 4T com trimestre e ano lado a lado;
"no período" sem definir qual.
*Ação:* não atribua `periodicidade` e não atribua `periodo_fiscal`. Pendência.

**8. Narrativa diverge da tabela**
*Sintoma:* o texto diz "quase R$ 10 bilhões", a tabela diz `9.856,4` em R$ milhões, e a
diferença ultrapassa o arredondamento esperado.
*Ação:* registre os dois fatos, cada um com sua evidência, e marque conflito. A preferência
pela tabela vale para precisão — não para apagar a divergência.

**9. Conclusão qualitativa forte**
*Sintoma:* uma afirmação do resumo que não decorre diretamente de um valor extraído —
atribuição de causa, comparação com concorrentes, juízo sobre tendência.
*Ação:* não afirme. Reescreva de forma descritiva ou marque para revisão. A análise descreve
o que os documentos reportam; explicar *por que* aconteceu é interpretação.

**10. Risco de soar como recomendação**
*Sintoma:* qualquer formulação que um leitor possa entender como conselho sobre comprar,
vender ou manter a ação — inclusive por adjetivação ("resultado sólido", "momento
favorável"), por projeção, ou por insinuação.
*Ação:* reescreva de forma estritamente factual. Persistindo a dúvida, marque para revisão.
Antes de fechar o resumo, releia-o procurando **especificamente** por isso — é o tipo de
frase que escapa quando se está lendo para conferir números.

---

## Parte 2 — Auditoria antes de concluir

Sem auditoria não há conclusão. O resultado é reportado mesmo quando desfavorável — uma
auditoria que só aparece quando passa não serve para nada.

Cada verificação vira uma linha na aba Auditoria, inclusive as que passaram.

### Escopo e seleção

| `check_id` | Verifica |
|---|---|
| `sel_quantidade` | quantidade de documentos analisados = `N` pedido; se menor, diferença declarada no Resumo |
| `sel_tipo` | todo documento analisado tem `tipo = release_resultados` |
| `sel_periodos_unicos` | nenhum período fiscal duplicado entre os documentos |
| `sel_ordenacao` | documentos e colunas em ordem cronológica crescente |
| `sel_periodo_origem` | período de cada documento veio do conteúdo, não do nome do arquivo |
| `sel_descartados` | documentos descartados estão registrados com motivo |

### Integridade da evidência

| `check_id` | Verifica |
|---|---|
| `evi_obrigatoria` | todo fato tem `documento_id`, `pagina` e `trecho_fonte` |
| `evi_contem_valor` | `trecho_fonte` contém `valor_original` |
| `evi_documento_existe` | todo `documento_id` citado existe na aba Documentos |
| `evi_rastro_comparativo` | toda linha do Comparativo resolve para ≥1 linha de Evidências |
| `evi_original_preservado` | `valor_original` presente e não modificado em todo fato |

### Valores e unidades

| `check_id` | Verifica |
|---|---|
| `val_null_nao_zero` | nenhuma ausência gravada como `0` ou string vazia |
| `val_null_coerente` | `valor_normalizado = null` sempre que `unidade = null` |
| `val_unidade_serie` | unidade coerente dentro de cada série |
| `val_sinal` | valores rotulados como prejuízo/queda têm sinal negativo |
| `val_pp_vs_pct` | `variacao_pp` só em séries `percentual`; `variacao_pct` nunca nelas |

### Comparação

| `check_id` | Verifica |
|---|---|
| `cmp_serie_integra` | nenhuma série mistura `métrica`, `segmento`, `base`, `periodicidade` ou `tipo_valor` |
| `cmp_n_posicoes` | toda série tem exatamente `N` posições, sem deslocamento |
| `cmp_denominador_zero` | nenhuma `variacao_pct` calculada sobre anterior = 0 |
| `cmp_confianca_baixa` | nenhuma variação calculada com ponta de confiança baixa |
| `cmp_texto` | séries `texto` não têm variação numérica |
| `cmp_base_declarada` | toda variação declara `base_comparacao` |

### Pendências e linguagem

| `check_id` | Verifica |
|---|---|
| `pen_conflitos` | todo conflito detectado tem pendência com todos os lados preservados |
| `pen_flags_coerentes` | `revisao_humana = true` ⟺ `flags` não vazio |
| `pen_visivel` | pendências aparecem na planilha e são mencionadas no Resumo |
| `lng_sem_recomendacao` | varredura do Resumo por linguagem de recomendação de investimento |
| `lng_sem_promocional` | varredura por adjetivação avaliativa e linguagem promocional |

### Planilha

| `check_id` | Verifica |
|---|---|
| `xls_abas` | as seis abas existem, com nomes e ordem corretos |
| `xls_colunas_periodo` | Comparativo tem `N` colunas de período em ordem crescente |
| `xls_texto_preservado` | `valor_original` e `trecho_fonte` gravados como texto |
| `xls_reabertura` | arquivo reabre e as verificações acima passam sobre o conteúdo lido |

### Severidade e desfecho

- **`FAIL` de severidade alta** — integridade de evidência, `null` virando `0`, mistura de
  séries, linguagem de recomendação: a entrega não pode ser apresentada como concluída.
  Corrija ou declare o bloqueio.
- **`FAIL` de severidade média ou `ALERTA`** — registre na aba Auditoria e mencione no
  Resumo. Não silencie.
- **`N` obtido menor que `N` pedido** — não é falha da análise, mas é sempre declarado.

Ao relatar o resultado ao usuário, mostre o que a auditoria encontrou — inclusive o que
falhou. Alegar conclusão sem apresentar a auditoria contradiz a razão de existir de todo
este procedimento.
