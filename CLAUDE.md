# CLAUDE.md — vc-master-releases-magalu

Regras permanentes deste repositório. Valem para toda sessão e toda tarefa.

O **procedimento de análise dos releases** não está aqui: ele mora na skill específica do
projeto (ver *Uso das skills*). Este arquivo define como se trabalha no repositório, não
como se analisa um release.

---

## Objetivo do projeto

Analisar releases de resultados da **Magazine Luiza** a partir de uma única entrada
principal: a quantidade `N` de releases mais recentes a analisar.

A execução parte da Central de Resultados oficial da companhia, seleciona os `N` releases
de resultados mais recentes por **período fiscal**, extrai os indicadores financeiros e
operacionais com evidência rastreável, compara os períodos e entrega os resultados.

O **artefato final principal é uma planilha Excel**. O resumo executivo, as evidências e os
itens de revisão humana acompanham essa entrega.

`N` é sempre parâmetro de execução. Qualquer valor de `N` deve funcionar **sem alteração
manual no código**. Valor de `N` fixo em código-fonte é defeito.

---

## Escopo

Nesta versão, o escopo é fechado:

**Dentro do escopo**
- Empresa fixa: Magazine Luiza.
- Fonte fixa: Central de Resultados oficial da companhia.
- Quantidade de releases configurável via parâmetro.
- Somente PDFs textuais.

**Fora do escopo — não implementar, não sugerir como atalho**
- OCR.
- Banco de dados.
- Aplicação web.
- Chamadas a APIs de LLM dentro do código Python.
- Outras empresas ou outras fontes de dados.

**Proibição de conteúdo**

O projeto **não emite recomendação de compra, venda ou manutenção de investimentos**, em
nenhum artefato: código, planilha, resumo executivo, comentário ou resposta em chat. A
entrega é descritiva, comparativa e rastreável. Qualquer texto gerado deve se limitar ao
que os documentos reportam.

Ampliação de escopo exige pedido explícito do usuário. Não antecipar funcionalidades
"porque seria útil".

---

## Ambiente do projeto

- **Python 3.12** — o ambiente atual é `Python 3.12.8` (CPython, isolado do sistema).
- **Usar exclusivamente o `.venv` existente na raiz do repositório.**
- **Nunca criar outro ambiente virtual.** Sem `venv`, `virtualenv`, `conda`, `uv venv`,
  `poetry`, ou ambiente temporário — nem para testar, nem para isolar, nem "rapidinho".
- Se o `.venv` parecer quebrado ou faltar algo, **parar e relatar ao usuário**. Não
  recriar por conta própria.

**Interpretador e comandos** (Windows / PowerShell):

```
.venv\Scripts\python.exe          # sempre este interpretador
.venv\Scripts\python.exe -m pip   # sempre pip como módulo deste interpretador
.venv\Scripts\python.exe -m pytest
```

Nunca invocar `python`, `pip` ou `pytest` diretamente do PATH — eles podem apontar para
outro interpretador.

**Dependências**
- Instalar somente o necessário, e somente após o usuário aprovar o plano da tarefa.
- Preferir bibliotecas já presentes no `.venv` antes de adicionar novas.
- `requirements.txt` é gerado **ao final**, a partir das dependências **realmente
  utilizadas** pelo código — não a partir de um dump completo do ambiente.

---

## Processo de trabalho do agente

Ordem obrigatória para toda tarefa relevante:

1. **Analisar o objetivo** da tarefa e o estado real do repositório antes de propor algo.
2. **Apresentar um plano** ao usuário.
3. **Aguardar aprovação. Não iniciar a implementação antes do "sim".**
4. **Depois de aprovado, executar o plano de forma autônoma**, sem pedir confirmação a
   cada passo.
5. **Auditar o resultado** e relatar honestamente o que foi feito, o que ficou de fora e o
   que falhou.

Regras de conduta:
- O portão de aprovação é do **plano**, não do tamanho da tarefa. Tarefa pequena tem plano
  curto — não tem "plano nenhum".
- Se o escopo crescer no meio da execução, **parar e replanejar** com o usuário.
- Fazer exatamente o que foi pedido. Não reduzir, não expandir, não transformar o pedido.
- Se algo estiver bloqueado, concluir todo o restante e **declarar explicitamente** o que
  ficou pendente e por quê.
- Nunca declarar uma tarefa concluída sem evidência de execução (saída de teste, saída de
  comando, arquivo gerado).

---

## Uso das skills

- O desenvolvimento em Python segue **`superpowers:using-superpowers`** e as skills de
  processo que ela indica — em especial `brainstorming` (antes de criar) e
  `test-driven-development` (durante a implementação).
- A análise dos releases do Magalu é guiada por uma **skill específica do projeto**,
  criada com **`skill-creator`**. Essa skill é a fonte de verdade do procedimento de
  análise.
- **Qualquer tarefa dentro do projeto consulta essa skill como guia** antes de agir.
  Divergência entre o código e a skill é defeito a ser reportado, não resolvido por
  improviso.
- Regra de precedência quando houver conflito:
  **instruções do usuário → CLAUDE.md → skill do projeto → demais skills → comportamento
  padrão.**
- A skill do projeto descreve o procedimento de análise; o CLAUDE.md descreve as regras do
  repositório. Não duplicar conteúdo entre os dois: procedimento novo vai para a skill.

---

## Regras de engenharia

- **TDD é obrigatório**: teste que falha primeiro, depois o código que o faz passar.
  Código de produção escrito antes do teste deve ser refeito pelo ciclo correto.
- **Código Python cobre apenas as etapas determinísticas** — coleta, parsing, extração,
  normalização, comparação, geração de planilha, validação. Julgamento e interpretação não
  são embutidos como chamada de LLM no código.
- Módulos pequenos e de responsabilidade única, com fronteiras explícitas: cada unidade
  deve ser compreensível e testável isoladamente.
- Sem valores fixos de `N`, de ano, de trimestre ou de URL de documento espalhados pelo
  código. Configuração fica em um único lugar.
- Falhar alto e claro: erro de rede, PDF ilegível ou estrutura inesperada devem produzir
  erro explícito, **nunca** um valor silenciosamente preenchido ou um resultado parcial
  apresentado como completo.
- Nada de rede dentro dos testes automatizados. Rede é isolada atrás de uma fronteira e
  substituída por fixtures nos testes.
- Não reescrever nem refatorar o que está fora do objetivo da tarefa atual.

---

## Confiabilidade dos dados

Estas regras não admitem exceção.

- **Nunca inventar, estimar, interpolar ou completar valores sem evidência no documento.**
- Dado ausente é **`null`** — nunca `0`, nunca string vazia, nunca "aproximadamente".
- Preservar sempre **valor original** (como aparece no documento) **e valor normalizado**.
- Todo valor carrega seu rastro: **documento, período, página, trecho-fonte, unidade e
  confiança**.
- Distinguir explicitamente, sem misturar:
  - **ajustado** × **reportado**;
  - **trimestre isolado** × **acumulado** × **anual**;
  - **valor absoluto** × **percentual** × **variação**;
  - **consolidado** × **lojas físicas** × **e-commerce** × **marketplace** × **1P** × **3P**.
- **Sinalizar** conflitos entre fontes, ambiguidades de interpretação e valores de baixa
  confiança — em vez de escolher um silenciosamente.
- **Exigir revisão humana** quando a evidência for insuficiente, contraditória ou ambígua.
  Marcar o item, não adivinhar.
- Registrar dados ausentes e itens para revisão humana como **saída de primeira classe**,
  visível na entrega — não como aviso enterrado em log.

---

## Validação

- A execução **audita os resultados antes de concluir**. Sem auditoria, não há conclusão.
- A auditoria confere, no mínimo: quantidade de releases igual a `N`; períodos fiscais
  corretos, ordenados e sem duplicatas; toda célula de valor com evidência associada;
  ausências marcadas como `null`; unidades coerentes entre períodos comparados.
- Testes automatizados devem passar antes de qualquer alegação de conclusão.
  Rodar via `.venv\Scripts\python.exe -m pytest` e **mostrar a saída**.
- Alegação de "funcionando", "corrigido" ou "pronto" só com evidência de execução colada
  na resposta. Se um teste falhar, dizer que falhou e mostrar a saída.
- Nunca ajustar teste ou expectativa apenas para ficar verde.
- Discrepância encontrada na auditoria é reportada ao usuário, não silenciada.

---

## Versionamento

- **Este diretório ainda não é um repositório git.** Não executar `git init`, não criar
  commits e não configurar remoto sem pedido explícito do usuário.
- Quando o versionamento for habilitado, valem as regras padrão: nunca commitar sem
  pedido; nunca usar `--no-verify`; preferir commit novo a `--amend`.
- **Nunca versionar**: `.venv/`, PDFs baixados, planilhas geradas, caches e quaisquer
  artefatos de execução. Esses arquivos são reproduzíveis a partir do código.
- **Versionar**: código-fonte, testes, fixtures de teste, `CLAUDE.md`, a skill do projeto e
  o `requirements.txt`.
- Artefatos de saída são identificados por execução — empresa, `N`, períodos analisados e
  data/hora — de modo que uma execução nunca sobrescreva silenciosamente a anterior.
- `requirements.txt` é versionado com versões fixadas e atualizado sempre que uma
  dependência realmente utilizada mudar.
