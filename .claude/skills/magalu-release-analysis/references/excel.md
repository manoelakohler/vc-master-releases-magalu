# Excel — estrutura e validação

O Excel é o artefato final principal. Ele precisa sustentar uma pergunta feita por alguém
que não acompanhou a execução: *"de onde veio este número?"* — e a resposta tem que estar na
própria planilha.

**Regra que atravessa todas as abas:** a partir de qualquer número exibido, é possível chegar
a uma linha da aba **Evidências** com documento, página e trecho. Número sem esse caminho não
entra.

Para construir e validar o arquivo, use a skill **`document-skills:xlsx`**. Esta skill define
*o quê*; a de planilhas ensina *como* manipular o formato; o código Python do repositório
executa. Não escreva manipulação de xlsx do zero.

---

## As seis abas, nesta ordem

### 1. Resumo

Bloco de cabeçalho da execução, seguido do resumo executivo e de um quadro de destaques.

**Cabeçalho:** empresa · `N` pedido · `N` obtido · períodos analisados (ordem crescente) ·
documentos utilizados · fonte · data/hora da execução · total de pendências abertas ·
resultado da auditoria.

`N` pedido e `N` obtido são campos separados de propósito. Quando diferem, a diferença
precisa ser visível na primeira tela, não descoberta depois.

**Resumo executivo:** na estrutura de seis partes definida no SKILL.md — escopo, o que os
números mostram, variações relevantes, conflitos e ambiguidades, lacunas, itens de revisão.

**Quadro de destaques:**

| Coluna | Conteúdo |
|---|---|
| `metrica_rotulo` | rótulo do documento |
| `segmento`, `base`, `periodicidade` | as dimensões da série |
| `periodo_mais_recente` | rótulo |
| `valor` + `unidade` | do período mais recente |
| `variacao` + `tipo_variacao` | `abs` / `pct` / `pp` |
| `base_comparacao` | contra o quê |
| `evidencias` | quantidade de fatos que sustentam a linha |
| `revisao` | sinalizador |

### 2. Comparativo

Uma linha por **série**. As colunas de período vêm **em ordem cronológica crescente** e são
geradas a partir de `N` — nunca fixas.

| Bloco | Colunas |
|---|---|
| Identificação | `serie_id`, `metrica_id`, `metrica_rotulo`, `segmento`, `base`, `periodicidade`, `tipo_valor`, `unidade_serie` |
| Períodos | uma coluna por período, ordem crescente, rótulo no cabeçalho |
| Variações | `variacao_abs`, `variacao_pct`, `variacao_pp`, `base_comparacao`, `calculada`, `motivo_nao_calculada` |
| Qualidade | `confianca_minima`, `evidencias`, `revisao_humana`, `pendencias` |

Toda série tem as `N` colunas de período preenchidas ou explicitamente vazias. Nenhuma série
"encolhe" por falta de dado.

`variacao_pp` só é preenchida para `tipo_valor = percentual`; `variacao_pct` nunca é.

### 3. Evidências

Uma linha por **registro de fato**, com todos os campos do contrato de dados. É a aba que
sustenta as outras.

`fato_id` · `metrica_id` · `metrica_rotulo` · `segmento` · `base` · `periodicidade` ·
`tipo_valor` · `periodo_fiscal` · `periodo_rotulo` · `valor_original` · `valor_normalizado` ·
`unidade` · `documento_id` · `pagina` · `trecho_fonte` · `confianca` · `flags` ·
`revisao_humana` · `motivo`

`valor_original` e `trecho_fonte` vão como **texto**, sem qualquer conversão automática do
Excel. Deixar o Excel interpretar `1.234,5` ou `(1.234)` destrói exatamente a coluna que
existe para provar o que o documento dizia.

### 4. Documentos

Uma linha por PDF, com os campos do contrato: `documento_id` · `titulo` · `tipo` ·
`periodo_fiscal` · `periodo_rotulo` · `url_origem` · `nome_servidor` · `data_publicacao` ·
`arquivo_local` · `bytes` · `sha256` · `paginas` · `textual` · `baixado_em`.

`nome_servidor` é o nome com que o servidor devolveu o arquivo (`Content-Disposition`). Na
Central os links são tokens opacos que nada dizem sobre o documento: esse nome é a
confirmação independente de que o PDF baixado é o release daquele período. Divergência
entre ele e o período da listagem é pendência, não detalhe de nomenclatura.

Inclua também os documentos **descartados** — com `tipo` e o motivo do descarte. Saber o que
foi deixado de fora é parte de saber o que a análise cobre.

### 5. Pendências

Uma linha por item de revisão: `pendencia_id` · `tipo` · `severidade` · `descricao` ·
`referencias` · `valores_conflitantes` · `acao_sugerida` · `status`.

Ordene por severidade decrescente. Em conflitos, `valores_conflitantes` traz **todos os
lados** com suas evidências — a aba não escolhe vencedor.

Se não houver pendências, a aba existe com cabeçalho e uma linha declarando explicitamente
que nenhuma foi registrada. Aba vazia é ambígua: não se sabe se nada foi encontrado ou se a
verificação não rodou.

### 6. Auditoria

Uma linha por verificação executada: `check_id` · `descricao` · `esperado` · `obtido` ·
`resultado` · `severidade` · `detalhe`.

Inclua as verificações que passaram. A aba precisa provar que a auditoria rodou, não apenas
listar o que deu errado.

O checklist está em `revisao-e-auditoria.md`.

---

## Apresentação

**`null` nunca vira `0`.** Célula vazia com marcação visual discreta e consistente. Se houver
motivo registrado, ele aparece em coluna própria ou como comentário — nunca substituindo o
valor.

**Unidade em coluna própria**, nunca embutida no número nem só no cabeçalho. Cabeçalho se
perde quando alguém filtra, copia ou reordena.

**Textos literais como texto.** `valor_original`, `trecho_fonte`, `periodo_rotulo` e
identificadores entram com formato de texto explícito. O Excel converte `1.234,5` em data,
em número anglófono ou em coisa pior dependendo do locale da máquina que abrir o arquivo.

**Números normalizados como número**, com a precisão do documento preservada — sem
arredondar para "ficar bonito".

**Ordem crescente de período** em toda a planilha, sem exceção.

**Cabeçalhos congelados** e filtro nas abas longas (Comparativo, Evidências, Pendências).

**Nenhuma fórmula viva** para valores que vieram dos documentos. A planilha é registro
auditável, não modelo recalculável: uma fórmula que recalcula pode divergir do que foi
extraído e auditado.

---

## Validação do arquivo gerado

Depois de gravar, **reabra o arquivo e verifique** — gravar sem erro não prova que o
conteúdo está correto:

- as seis abas existem, com os nomes e na ordem definida
- a aba Comparativo tem exatamente `N` colunas de período, em ordem crescente
- toda linha do Comparativo referencia pelo menos uma linha de Evidências
- todo `documento_id` citado em Evidências existe na aba Documentos
- nenhuma célula de valor ausente foi gravada como `0`
- `valor_original` e `trecho_fonte` estão como texto e não foram reinterpretados
- o cabeçalho do Resumo mostra `N` pedido e `N` obtido
- a aba Auditoria tem linhas e a aba Pendências não está silenciosamente vazia

Falha em qualquer item é reportada, não corrigida por remendo na apresentação.
