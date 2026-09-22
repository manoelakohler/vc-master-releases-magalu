# Catálogo de indicadores — releases Magalu

## Como usar este catálogo

Esta é uma **lista de alvos de busca**, não uma lista de coisas que devem existir no
documento. Ela responde "o que procurar e como reconhecer", nunca "qual é o valor".

Três consequências práticas:

- Indicador do catálogo que não aparece no release é **`null`**. Não é falha de extração,
  não autoriza procurar em outra fonte, não autoriza derivar por cálculo.
- Indicador que aparece no release e **não** está no catálogo pode ser extraído. O catálogo
  é o mínimo, não o teto.
- Os rótulos variam entre releases. Reconheça pelo conceito e pelos sinônimos, mas **grave
  sempre o rótulo literal** que o documento usou, em `metrica_rotulo`.

Toda extração precisa fixar, além do valor: **segmento**, **base** (reportado/ajustado),
**periodicidade** (trimestre/acumulado/anual) e **tipo_valor**. Um mesmo nome de métrica
gera séries diferentes conforme essas dimensões — ver `contrato-de-dados.md`.

---

## Conjunto inicial

### Núcleo financeiro (12)

| `metrica_id` | Conceito | Sinônimos frequentes | Tipo |
|---|---|---|---|
| `vendas_totais` | Vendas totais / GMV total | "vendas totais", "GMV", "vendas brutas totais" | absoluto |
| `receita_liquida` | Receita líquida | "receita líquida", "receita operacional líquida", "ROL" | absoluto |
| `lucro_bruto` | Lucro bruto | "lucro bruto", "resultado bruto" | absoluto |
| `margem_bruta` | Margem bruta | "margem bruta", "% da receita líquida" na linha do lucro bruto | percentual |
| `despesas_operacionais` | Despesas com vendas, gerais e administrativas | "despesas operacionais", "SG&A", "despesas com vendas" + "gerais e administrativas" | absoluto |
| `ebitda` | EBITDA | "EBITDA" | absoluto |
| `ebitda_ajustado` | EBITDA ajustado | "EBITDA ajustado" | absoluto |
| `margem_ebitda` | Margem EBITDA | "margem EBITDA", "% da receita líquida" na linha do EBITDA | percentual |
| `resultado_financeiro` | Resultado financeiro líquido | "resultado financeiro", "despesas financeiras líquidas" | absoluto |
| `lucro_liquido` | Lucro (prejuízo) líquido reportado | "lucro líquido", "prejuízo líquido", "resultado líquido" | absoluto |
| `lucro_liquido_ajustado` | Lucro (prejuízo) líquido ajustado | "lucro líquido ajustado", "resultado líquido ajustado" | absoluto |
| `margem_liquida` | Margem líquida | "margem líquida" | percentual |

### Complementar financeiro (8)

| `metrica_id` | Conceito | Sinônimos frequentes | Tipo |
|---|---|---|---|
| `ebit` | Resultado operacional / EBIT | "EBIT", "resultado operacional", "lucro operacional" | absoluto |
| `depreciacao_amortizacao` | Depreciação e amortização | "depreciação e amortização", "D&A" | absoluto |
| `divida_liquida` | Dívida líquida ou caixa líquido | "dívida líquida", "caixa líquido", "posição de caixa ajustada", "endividamento líquido" | absoluto |
| `capital_giro` | Capital de giro | "capital de giro", "necessidade de capital de giro" | absoluto |
| `fluxo_caixa_operacional` | Fluxo de caixa operacional | "fluxo de caixa operacional", "caixa gerado nas operações", "FCO" | absoluto |
| `fluxo_caixa_livre` | Fluxo de caixa livre | "fluxo de caixa livre", "FCL", "geração de caixa livre" | absoluto |
| `capex` | Investimentos | "CAPEX", "investimentos", "aquisição de imobilizado e intangível" | absoluto |
| `estoques` | Estoques | "estoques", "prazo médio de estoques", "giro de estoques" | absoluto |

### Operacional (8)

| `metrica_id` | Conceito | Sinônimos frequentes | Tipo |
|---|---|---|---|
| `vendas_lojas_fisicas` | Vendas em lojas físicas | "vendas em lojas físicas", "lojas físicas", "canal físico" | absoluto |
| `vendas_ecommerce` | Vendas em e-commerce (total) | "e-commerce", "vendas online", "canal digital" | absoluto |
| `vendas_1p` | Vendas 1P (estoque próprio online) | "1P", "e-commerce próprio", "vendas próprias" | absoluto |
| `vendas_3p` | GMV 3P / marketplace | "3P", "marketplace", "GMV de terceiros" | absoluto |
| `mesmas_lojas` | Crescimento em mesmas lojas | "mesmas lojas", "same-store sales", "SSS" | percentual |
| `numero_lojas` | Número de lojas | "número de lojas", "total de lojas", por formato (convencionais, virtuais, quiosques) | absoluto |
| `clientes_ativos` | Base de clientes ativos | "clientes ativos", "base de clientes" | absoluto |
| `sellers_marketplace` | Sellers no marketplace | "sellers", "vendedores parceiros", "lojistas" | absoluto |

### Oportunistas

Extraia quando o release os apresentar, mas nunca abra pendência por ausência: receita de
serviços, Magalu Ads, TPV de pagamentos, usuários ativos do aplicativo, take rate do 3P,
NPS, número de SKUs/itens ofertados, área de vendas, aberturas e fechamentos de lojas,
número de colaboradores, resultado de operações financeiras associadas.

---

## Armadilhas do domínio

Cada item abaixo já causou erro real em análises deste tipo. Elas não são curiosidades —
são as verificações que separam uma planilha confiável de uma perigosa.

### Vendas totais (GMV) não são receita

`vendas_totais` e `receita_liquida` medem coisas diferentes e têm ordens de grandeza
diferentes. O GMV de marketplace (`vendas_3p`) em particular **não é receita da companhia**
— dele a empresa reconhece comissão, não o valor da mercadoria. Somar, comparar ou
apresentar lado a lado como se fossem a mesma família é o erro mais comum do setor.

Mantenha-os em séries separadas. Sempre.

### Ajustado nunca se mistura com reportado

O Magalu reporta EBITDA e lucro líquido em duas versões: reportado e ajustado (este último
excluindo itens não recorrentes). A diferença entre elas pode ser grande o bastante para
inverter o sinal do resultado.

Se o rótulo na página não deixa claro qual é, `base = indefinido` e abre pendência. Não
assuma que "EBITDA" isolado significa reportado quando a mesma página contém também o
ajustado — releases costumam usar o nome curto em narrativa e o nome completo em tabela.

### Consolidado, canais e segmentos

`consolidado` ≠ `lojas_fisicas` + `ecommerce` necessariamente, e `ecommerce` ≠ `1p` + `3p`
necessariamente — depende do que a companhia consolida naquele release e de operações fora
desses canais. **Não reconstrua totais por soma.** Se o total não está impresso, é `null`.

### Narrativa arredonda, tabela não

O texto corrido diz "quase R$ 10 bilhões"; a tabela diz `9.856,4` em R$ milhões. São o mesmo
fato com precisões diferentes.

Prefira a tabela quando as duas existirem. Se divergirem além do arredondamento esperado,
isso é **conflito narrativa × tabela** — registre os dois valores e abra pendência, não
escolha silenciosamente.

### Reapresentação entre releases (o conflito mais provável)

Ao analisar `N` releases, o mesmo período aparece em mais de um documento: o 2T25 está no
release do 2T25 e também como comparativo no release do 3T25. A companhia pode **reapresentar**
um número (mudança contábil, reclassificação, correção).

Quando os dois valores divergem, **ambos estão certos no contexto de seu documento**. Registre
as duas evidências, marque conflito e deixe a escolha para revisão humana. Sobrescrever o
antigo pelo novo sem registro apaga a informação mais interessante da análise.

### Percentual, ponto percentual e variação

Margem é percentual; a diferença entre duas margens é em **pontos percentuais**. O release
escreve `p.p.` justamente para marcar isso. Tratar `p.p.` como `%` (ou vice-versa) produz
número errado com aparência correta — ver `periodos-e-numeros.md`.

### Sinal e prejuízo

Prejuízo aparece entre parênteses, com sinal negativo, ou pela palavra "prejuízo" com número
positivo. Os três casos significam valor negativo. Perder o sinal transforma prejuízo em
lucro — verifique contra o rótulo, não só contra o formato.

### Um número, várias colunas

Tabelas de release trazem o trimestre, o mesmo trimestre do ano anterior, a variação, o
acumulado do ano e o acumulado anterior — na mesma linha. Pegar a coluna errada é fácil e
invisível.

Ancore sempre no cabeçalho de coluna. Se o cabeçalho se perdeu na extração, não atribua
período: é tabela sem estrutura, gatilho de revisão.
