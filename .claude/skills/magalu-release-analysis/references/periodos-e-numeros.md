# Período fiscal, unidades e formato numérico

Este arquivo cobre as duas fontes de erro silencioso mais graves da análise: **atribuir o
período errado** a um valor certo, e **converter mal um número** brasileiro. Nos dois casos
o resultado final parece perfeitamente plausível.

---

## Período fiscal

### Notação usada nos releases

| No documento | Significa | Periodicidade |
|---|---|---|
| `1T25`, `2T25`, `3T25`, `4T25` | trimestre isolado de 2025 | `trimestre` |
| `1T2025`, `2Q25`, `Q2 2025` | mesma coisa, grafias alternativas | `trimestre` |
| `6M25`, `9M25`, `1S25` | acumulado do ano até o período | `acumulado` |
| `12M25`, `2025`, "exercício de 2025" | ano completo | `anual` |
| "acumulado do ano", "no ano", "YTD" | acumulado | `acumulado` |

O ano aparece com dois dígitos (`2T25`) ou quatro (`2T2025`). Dois dígitos são sempre
`20XX` neste contexto.

### Forma canônica

Guarde duas representações:

- `periodo_fiscal`: canônico e ordenável — `2025-Q2`, `2025-9M`, `2025-FY`
- `periodo_rotulo`: como o documento escreveu — `2T25`

A ordenação usa o canônico. O rótulo existe para exibição e para auditoria.

Ordene por **(ano, trimestre)**. Trimestres isolados ordenam Q1 < Q2 < Q3 < Q4. Séries de
periodicidades diferentes não se ordenam juntas porque não se comparam — cada série tem sua
própria linha do tempo.

### O período vem do documento

Nunca do nome do arquivo, nunca da data de publicação, nunca da posição na listagem do site.

O release do 4T é publicado no ano seguinte, normalmente em fevereiro ou março. Ordenar por
data de publicação coloca o 4T24 depois do 1T25 e embaralha toda a série — e o resultado
continua parecendo uma lista ordenada.

Se o período não puder ser determinado com segurança a partir do conteúdo do documento, ele
**não é chutado**: o documento entra como pendência de classificação.

### O release de 4T é um caso especial

O documento do quarto trimestre costuma apresentar, nas mesmas tabelas, o **trimestre
isolado** (4T) e o **ano completo** (12M). As duas colunas ficam lado a lado e usam os
mesmos rótulos de métrica.

Portanto, ao extrair de um release de 4T, a decisão de `periodicidade` é obrigatória e
explícita para cada valor. Na dúvida sobre qual coluna originou o número, isso é o gatilho
"dúvida entre trimestre e acumulado": não atribua, abra pendência.

### Duplicatas e lacunas

- **Dois documentos para o mesmo período**: registre ambos, abra pendência, não escolha.
  O período, porém, ocupa **uma única posição** na comparação: a régua é de períodos, não
  de documentos. Repetido, o mesmo trimestre viraria duas colunas idênticas que o leitor
  entende como períodos diferentes.
- **Período faltando no meio da série** (ex.: `N=4` mas só existem 1T25, 2T25 e 4T25):
  a série mantém a posição vazia como `null`. Não deslize os valores para fechar o buraco —
  é assim que uma série inteira passa a comparar períodos errados.

---

## Unidades

### As que aparecem

`R$ mil` · `R$ milhões` · `R$ bilhões` · `%` · `p.p.` · `unidades` · `lojas` · `sellers` ·
`clientes` · `dias` (prazos médios) · `x` (múltiplos, ex.: dívida/EBITDA)

### Onde a unidade mora

Quase nunca junto do número. Ela vem de:

1. cabeçalho da tabela — `(R$ milhões)`
2. título da seção
3. nota de rodapé
4. narrativa em volta

Isso significa que a unidade pode estar a vários centímetros do valor na página, e que a
extração de texto pode separar os dois. **Se a unidade não estiver inequívoca para aquele
número específico, `valor_normalizado` fica `null` e abre-se pendência.**

Um número certo em unidade errada é mil vezes pior que um número ausente: `9.856,4` em
milhões e `9.856,4` em milhares diferem por um fator de mil e ambos parecem razoáveis numa
planilha.

### Escala na mesma série

Uma série pode mudar de escala entre releases (tabela em milhares num documento, em milhões
noutro). Normalize para uma escala única **por série** e registre a escala usada. Auditoria
verifica coerência de unidade dentro de cada série.

### `%` e `p.p.` não são a mesma coisa

- `%` é um nível: margem bruta de `28,4%`.
- `p.p.` é uma diferença entre dois níveis: de `26,1%` para `28,4%` são `+2,3 p.p.`

Tratar um como o outro produz número errado com aparência correta. Quando o documento
escreve `p.p.`, o `tipo_valor` é `variacao_pp` — não `percentual`.

---

## Formato numérico brasileiro

**Esta é a regra mais importante deste arquivo.**

Nos releases, o separador de **milhar é o ponto** e o separador **decimal é a vírgula**:

```
1.234,5      → 1234.5
9.856,4      → 9856.4
12,3         → 12.3
1.234.567    → 1234567
36,7%        → 36.7  (unidade %)
```

Aplicar a convenção anglófona a `1.234,5` produz `1.234` — erro de fator mil, e o número
resultante continua parecendo plausível. É o erro mais destrutivo possível neste domínio.

### Sinal negativo

Três formas, todas significando valor negativo:

```
(1.234,5)    → -1234.5     parênteses, uso contábil
-1.234,5     → -1234.5     sinal explícito
1.234,5      → -1234.5     quando o rótulo diz "prejuízo"
```

O terceiro caso exige ler o rótulo, não só o formato. Perder o sinal transforma prejuízo em
lucro.

### Marcadores de ausência

`-` · `—` · `n.a.` · `n.d.` · `n/a` · célula vazia

Todos viram **`null`**, nunca `0`. O documento está dizendo "não se aplica" ou "não
disponível", e zero é um valor reportável e diferente disso.

### O que preservar

`valor_original` guarda o texto literal, sem tocar: `"R$ 9.856,4"`, `"(1.234)"`,
`"+2,3 p.p."`, `"n.a."`. É ele que permite a um humano auditar a normalização sem reabrir o
PDF.

### Sequência de normalização

1. Capture o texto literal → `valor_original`
2. Determine a unidade a partir do contexto. Ambígua? → `valor_normalizado = null` + pendência
3. Determine o sinal (parênteses, sinal, rótulo)
4. Converta ponto→milhar, vírgula→decimal
5. Aplique a escala da unidade
6. Registre `unidade` explicitamente ao lado do valor

Nenhum passo é opcional, e o passo 2 é o que mais frequentemente termina em `null` — o que
está correto.
