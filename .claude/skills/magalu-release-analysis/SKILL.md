---
name: magalu-release-analysis
description: Procedimento e conhecimento de domínio para analisar releases de resultados da Magazine Luiza (Magalu) a partir da Central de Resultados oficial. Use sempre que a tarefa envolver releases, resultados trimestrais, 1T/2T/3T/4T, indicadores financeiros ou operacionais do Magalu, comparação entre trimestres, extração de valores de PDFs de resultados, ou geração da planilha de análise — inclusive quando o pedido for indireto ("analise os 3 últimos resultados", "compara os trimestres", "o que mudou no EBITDA"). Também use ao escrever, revisar ou testar qualquer código deste repositório, porque a skill define o contrato de dados, as regras de evidência e o formato do Excel que o código deve produzir.
---

# Análise de releases de resultados — Magazine Luiza

## Por que esta skill existe

Uma análise de resultados é lida por alguém que vai tomar decisão com ela. O erro que
destrói valor aqui não é a lacuna — é o número plausível e errado. Uma célula vazia é
visível e alguém a investiga; um número inventado, estimado ou trocado de unidade parece
certo e ninguém o questiona.

Por isso o produto desta skill não é "um conjunto de números". É **um conjunto de fatos com
rastro**: cada valor sabe de qual documento veio, de qual página, de qual trecho, em qual
unidade e com qual confiança. Um número sem rastro não entra no resultado — vira pendência.

Tudo o que se segue existe para sustentar isso.

## Quando usar

Sempre que a tarefa tocar releases de resultados do Magalu: descobrir documentos, escolher
os N mais recentes, extrair indicadores, comparar períodos, escrever o resumo, gerar ou
validar a planilha.

Também ao escrever, revisar ou testar código deste repositório: esta skill é a fonte de
verdade do contrato de dados e do formato de saída. Se o código divergir dela, o defeito é
do código — reporte, não improvise.

As regras permanentes do repositório (ambiente, `.venv`, TDD, versionamento, aprovação de
plano) estão no `CLAUDE.md` e não são repetidas aqui.

## Entrada

Uma única entrada principal: **`N`**, a quantidade de releases mais recentes a analisar.

`N` é sempre parâmetro. Qualquer valor precisa funcionar. Se algo no fluxo só funciona para
um `N` específico — uma ordenação assumida, um par fixo de períodos, uma coluna hardcoded —
isso é defeito.

## Fluxo operacional

As etapas 1–6 são determinísticas e pertencem ao código Python. As etapas 7–11 são guiadas
por esta skill. Nenhuma etapa pode ser pulada porque "o dado parece óbvio".

### 1. Descobrir os documentos na fonte oficial

A fonte é a **Central de Resultados oficial da Magazine Luiza**, no site de Relações com
Investidores da própria companhia. Nenhuma outra fonte é aceita: nem agregador, nem
notícia, nem PDF de terceiro, nem cache de buscador. Se o documento não veio da fonte
oficial, ele não entra.

O endereço exato e a forma de navegação são **configuração do projeto**, não conteúdo desta
skill — sites de RI mudam de estrutura e uma URL congelada aqui vira mentira silenciosa. O
que a skill exige é o critério: domínio oficial da companhia, seção de resultados,
documento publicado pela própria empresa.

Registre para cada documento encontrado: título, período declarado, URL, data de publicação
e tipo aparente.

### 2. Filtrar somente releases de resultados

A Central mistura vários tipos de documento. Só interessa o **release de resultados**
(também chamado "divulgação de resultados", "earnings release").

Fora: ITR e DFP, formulário de referência, demonstrações financeiras completas,
apresentações de resultados (slides), transcrições e áudios de teleconferência, fatos
relevantes, comunicados ao mercado, atas, avisos aos acionistas, relatórios de
sustentabilidade.

O critério de inclusão é **positivo**: o documento se identifica como release/divulgação de
resultados de um período. Documento cuja natureza você não consegue determinar a partir do
próprio documento **não** é incluído por eliminação — ele vira pendência de classificação.
Incluir um ITR como se fosse release contamina toda a comparação, porque a estrutura dos
números é diferente.

### 3. Determinar o período fiscal

Ano e trimestre vêm do documento, não do nome do arquivo e não da data de publicação. Um
release do 4T é publicado no ano seguinte; ordenar por data de publicação embaralha a série.

Detalhes de notação (`1T25`, `9M25`, `12M25`, "acumulado"), a forma canônica ordenável e o
tratamento do release de 4T — que traz trimestre e ano lado a lado — estão em
`references/periodos-e-numeros.md`. **Leia antes de implementar ou revisar qualquer
ordenação.**

Documento sem período determinável com segurança não é chutado: vira pendência.

### 4. Ordenar e selecionar

Ordene por **período fiscal** (ano, depois trimestre), nunca por data de publicação nem
pela ordem em que os itens aparecem na página. Selecione exatamente os `N` mais recentes.

Se existirem menos de `N` releases disponíveis, entregue os que existem e **declare a
diferença** explicitamente — no resumo, na auditoria e na resposta. Silenciar isso faz o
usuário acreditar que analisou mais período do que analisou.

Períodos duplicados (dois documentos para o mesmo trimestre) não são resolvidos por
escolha silenciosa: registre ambos e abra pendência.

### 5. Baixar os PDFs

Baixe da URL oficial. Para cada arquivo registre: caminho local, tamanho, SHA-256, número
de páginas e data/hora do download. O hash é o que permite a alguém verificar, meses
depois, que a análise se refere àquele arquivo exato.

Escopo: **somente PDFs textuais**. Se um PDF for digitalizado ou não devolver camada de
texto utilizável, ele não é processado e não é "resolvido" de outra forma — sem OCR, sem
transcrição manual, sem buscar o número em outro lugar. Registre como pendência e siga.

### 6. Extrair o texto preservando documento e página

A unidade de extração é **(documento, página)**. A página é o que torna a evidência
verificável por um humano em segundos — sem ela, "está no release" é inútil.

Quando a extração de texto colapsa uma tabela (colunas fundidas, números grudados, células
deslocadas), **não tente adivinhar o alinhamento**. Tabela com estrutura perdida é gatilho
de revisão humana. É melhor entregar `null` com pendência do que um número na linha errada,
porque o segundo erro é invisível.

### 7. Extrair os indicadores

O catálogo de indicadores — conjunto inicial, sinônimos usados pelo Magalu, e as armadilhas
de cada um — está em `references/indicadores.md`.

Cada valor extraído vira um **registro de fato** com evidência completa. O esquema está em
`references/contrato-de-dados.md`. É esse esquema que o código Python deve produzir e que
alimenta a aba Evidências da planilha.

O catálogo é uma **lista de alvos de busca**, não uma lista de coisas que devem existir. Um
indicador do catálogo que não aparece no documento é `null` — não é erro de extração e não
autoriza procurar em outro lugar.

### 8. Comparar

Regras completas na seção *Comparação*, adiante.

### 9. Escrever o resumo executivo

Regras completas na seção *Resumo executivo*, adiante.

### 10. Gerar o Excel

Estrutura das seis abas e suas colunas em `references/excel.md`.

### 11. Auditar antes de concluir

Checklist em `references/revisao-e-auditoria.md`. **Sem auditoria não há conclusão** — e o
resultado da auditoria é reportado mesmo quando desfavorável.

## Regras de interpretação

Estas regras não admitem exceção, e cada uma existe por um motivo concreto.

**Só os documentos são fonte de valor.** Nenhum valor pode vir de memória, de notícia, de
conhecimento geral sobre a empresa ou de outro release que não esteja no conjunto analisado.

**Conhecimento externo serve para procurar, nunca para preencher.** Saber que o Magalu
reporta "EBITDA Ajustado" ajuda a encontrar a linha certa na tabela. Isso é legítimo.
Escrever o valor do EBITDA porque você lembra a ordem de grandeza não é — é invenção com
aparência de competência. Se memória e documento divergirem, vale o documento. Se o
documento não tiver, o valor é `null`.

**Não inventar, não estimar, não interpolar, não inferir lacuna.** Calcular margem bruta
dividindo lucro bruto por receita líquida quando a margem não está impressa é inferência, e
não é permitido: a companhia pode calcular sobre outra base e o número derivado entraria na
planilha como se tivesse sido reportado. Valor derivado só existe quando o próprio documento
o apresenta.

**`null` para o que não foi encontrado.** Nunca `0`, nunca `"-"`, nunca `"n/d"`, nunca
string vazia no campo normalizado. Zero é um valor reportável e confundi-lo com ausência
corrompe qualquer variação calculada depois.

**Valor original preservado literalmente.** Guarde exatamente como aparece: `"R$ 9.856,4"`,
`"(1.234)"`, `"+2,3 p.p."`, `"36,7%"`. Sem limpar, sem converter, sem reformatar. É o
original que permite auditar a normalização.

**Normalizar apenas quando a unidade estiver inequívoca.** A unidade quase sempre vem de um
cabeçalho de tabela ou de uma nota — às vezes distante do número. Se ela não estiver clara,
`valor_normalizado` fica `null` e abre-se pendência. Um número certo em unidade errada é
mil vezes pior que um número ausente. As regras de formato numérico brasileiro estão em
`references/periodos-e-numeros.md` e **precisam ser lidas** antes de escrever qualquer
conversão: `1.234,5` é mil duzentos e trinta e quatro vírgula cinco, e inverter isso é o
erro mais destrutivo possível neste domínio.

**Métricas diferentes ficam em séries separadas.** A identidade de uma série é a tupla
`(métrica, segmento, base, periodicidade, tipo_valor)`. Lucro líquido ajustado nunca entra
na série do reportado. Trimestre isolado nunca entra na série do acumulado. Vendas de
e-commerce nunca entram na série do consolidado. Cada uma dessas misturas produz um gráfico
que parece coerente e conta uma história falsa.

**Não forçar comparação entre conceitos incompatíveis.** Comparar só acontece dentro da
mesma série. Se dois valores não compartilham a tupla inteira, eles não se comparam — nem
"só para ilustrar".

## Revisão humana

Marcar é sempre permitido. Adivinhar nunca é. Uma pendência bem descrita é entrega válida;
um número inventado é defeito.

São dez os gatilhos — confiança baixa, conflito, ambiguidade, unidade não clara, tabela sem
estrutura, dúvida entre ajustado e reportado, dúvida entre trimestre e acumulado,
divergência entre narrativa e tabela, conclusão qualitativa que depende de interpretação, e
risco de a linguagem soar como recomendação de investimento.

Cada gatilho, com seu sintoma observável e a ação correspondente, está em
`references/revisao-e-auditoria.md`. Consulte na etapa de extração e novamente antes de
fechar o resumo.

Pendências não são log. Elas são **saída de primeira classe**: aparecem na aba Pendências,
são contadas na auditoria e são mencionadas no resumo.

## Comparação

A comparação precisa funcionar para qualquer `N` — 2, 3 ou 12 — sem tratamento especial.

- **Ordem cronológica crescente**, sempre, em toda saída. Do período mais antigo para o mais
  recente. Isso vale para as colunas da planilha e para qualquer listagem.
- **Período ausente numa série é `null`.** A série mantém todas as `N` posições; ela não
  encolhe nem desloca os valores para preencher o buraco. Deslocamento silencioso é como
  uma série inteira passa a comparar períodos errados.
- **Valores originais e evidências permanecem acessíveis** ao lado do comparativo — a
  comparação nunca substitui o fato que a originou.
- **Monetários e quantidades**: variação absoluta e variação percentual.
- **Margens e percentuais**: variação em **pontos percentuais (p.p.)**. Variação percentual
  de um percentual é quase sempre um erro de leitura: de 10% para 12% são 2 p.p., não 20%
  no sentido que o leitor vai entender.
- **Valor anterior igual a zero → não calcular variação percentual.** O resultado é `null`
  com motivo registrado — não `0`, não infinito, não `-`.
- **Confiança baixa em qualquer uma das pontas → não calcular variação.** Uma variação
  herda a fragilidade do pior dos dois valores, e uma variação frágil parece tão sólida
  quanto qualquer outra na planilha.
- **Valores textuais comparam-se apenas qualitativamente.** Nunca aritmeticamente.
- **Declare a base de cada variação**: contra o período imediatamente anterior da série, ou
  contra o mesmo trimestre do ano anterior. São leituras diferentes e o leitor precisa saber
  qual está vendo.

## Resumo executivo

Factual, comparativo e ancorado em evidência. Estrutura:

```
1. Escopo analisado        — N pedido, N obtido, períodos, documentos, data da execução
2. O que os números mostram — por série, com período, valor e unidade
3. Variações relevantes     — com a base da variação declarada
4. Conflitos e ambiguidades — incluindo reapresentações entre releases
5. Lacunas                  — o que ficou null e por quê
6. Itens de revisão humana  — o que precisa de olho humano antes de uso
```

Toda afirmação numérica cita período e documento. Se um dado central estiver ausente, o
resumo **diz que está ausente**, em vez de contornar com uma frase que dá a impressão de
cobertura completa.

**Não use linguagem promocional nem avaliativa.** "Resultado sólido", "desempenho robusto",
"recuperação consistente", "momento favorável" — nada disso descreve um número, tudo isso
sugere um julgamento. Descreva direção e magnitude do que está impresso: *"a receita líquida
passou de X em 1T25 para Y em 2T25, variação de Z%"*.

**Nenhuma recomendação de compra, venda ou manutenção de investimento**, em nenhuma forma,
em nenhum idioma, nem por paráfrase ou insinuação. Isto vale para a planilha, para o resumo
e para qualquer resposta em chat sobre a análise. Antes de fechar o resumo, releia-o
procurando especificamente por frases que um leitor poderia ler como conselho — esse é um
dos dez gatilhos de revisão.

## Excel

O Excel é o artefato final principal. Seis abas, nesta ordem: **Resumo**, **Comparativo**,
**Evidências**, **Documentos**, **Pendências**, **Auditoria**.

Colunas, tipos, tratamento de `null` e regras de validação estão em `references/excel.md`.

Para construir e validar o arquivo, use a skill de planilhas disponível no ambiente
(**`document-skills:xlsx`**). A divisão de responsabilidades é: esta skill define **o quê**,
a skill de planilhas ensina **como** manipular o formato, e o código Python do repositório
**executa**. Não reinvente manipulação de xlsx à mão.

Regra que atravessa todas as abas: **nenhum número aparece na planilha sem que seja possível
chegar, a partir dele, até uma linha da aba Evidências** com documento, página e trecho.

## Dashboard

A execução também entrega um **dashboard HTML de página única**, gerado a partir da planilha
já gravada — nunca de dados em memória. Ler o artefato é o que garante que a página não possa
afirmar nada que o arquivo entregue não contenha.

Vale nele a mesma regra da planilha: **todo número exibido abre a sua evidência** — documento,
página e trecho literal. Ausência aparece como ausência, variação suprimida mostra o motivo, e
a auditoria aparece inteira, inclusive o que passou.

O arquivo é autocontido: sem CDN, sem fonte remota, sem script externo. Um relatório que
depende de rede para renderizar deixa de ser auditável exatamente quando alguém o abre meses
depois.

## Publicação

O dashboard é publicado como **artefato**, e quem publica é o agente — com a ferramenta de
artefatos, nunca o código. Chamada a serviço de LLM dentro do Python está fora de escopo, e
manter a publicação fora do pipeline é o que permite que a Fase C continue determinística e
testável sem rede.

O procedimento, depois de `relatar` aprovar a auditoria:

1. Publique o arquivo `dashboard_<run_id>.html` da execução como artefato.
2. Registre a URL na execução:
   `registrar-artefato --run <diretório> --url <url do artefato>`.
3. Informe que o artefato nasce **privado** — tornar público é ação de quem tem a conta, em
   claude.ai. Não declare como público o que não foi tornado público.

O registro existe porque o link precisa sobreviver à conversa: sem ele, a pasta da execução
deixa de explicar onde a página foi parar.

**A página publicada leva linha de autoria.** Uma página pública com o nome da companhia e
números dela pode ser lida como publicação oficial; a declaração de análise independente, com
a fonte citada, é o que impede essa leitura.

## Limites

- Somente PDFs textuais. **Sem OCR** — PDF digitalizado vira pendência.
- Sem banco de dados, sem aplicação web.
- **Sem chamadas a APIs de LLM dentro do código Python.** O julgamento acontece na condução
  da análise, guiado por esta skill; o código faz o que é determinístico.
- Empresa e fonte são fixas: Magazine Luiza, Central de Resultados oficial.
- **Nenhuma recomendação de investimento**, em nenhum artefato.

## Referências

| Arquivo | Leia quando |
|---|---|
| `references/indicadores.md` | for extrair indicadores ou decidir o que procurar |
| `references/periodos-e-numeros.md` | for tratar período fiscal, ordenação, unidade ou conversão numérica |
| `references/contrato-de-dados.md` | for escrever/revisar código que produz ou consome fatos |
| `references/excel.md` | for gerar ou validar a planilha |
| `references/revisao-e-auditoria.md` | for classificar pendências ou auditar antes de concluir |
