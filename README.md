# Análise de releases de resultados — Magazine Luiza

Recebe uma quantidade `N` e produz uma planilha Excel comparando os `N` releases de
resultados mais recentes da Magazine Luiza, com evidência rastreável para cada valor.

> **Não emite recomendação de compra, venda ou manutenção de investimentos.** A entrega é
> descritiva, comparativa e rastreável.

---

## O que este projeto garante

O erro que destrói valor numa análise de resultados não é a lacuna — é o número plausível e
errado. Uma célula vazia é visível e alguém investiga; um número inventado, estimado ou com
a unidade trocada parece certo e ninguém questiona.

Por isso o produto não é "um conjunto de números", e sim **um conjunto de fatos com rastro**:
cada valor sabe de qual documento veio, de qual página, de qual trecho, em qual unidade e
com qual confiança. Valor sem rastro não entra na planilha — vira pendência.

---

## Arquitetura: duas fases e um portão

Duas restrições do projeto se cruzam: a análise semântica é feita pelo agente, e o código
Python não faz chamadas a APIs de LLM. Disso decorre a arquitetura inteira.

```
  N ──▶  FASE A (Python)      descobre · classifica · ordena por período fiscal
                              seleciona N · baixa · SHA-256 · extrai texto por página
                                        │
                                        ▼  runs/<run_id>/dossie.md
                              ══════ PORTÃO SEMÂNTICO ══════
                                        │
         FASE B (agente)      lê o dossiê guiado pela skill magalu-release-analysis
                              grava fatos.json
                                        │
                                        ▼
         FASE C (Python)      valida contrato · séries · variações
                              Excel (6 abas) · dashboard HTML · auditoria (33 verificações)
```

O que a máquina fez é reproduzível byte a byte. O que exigiu leitura fica isolado num único
arquivo versionável e conferível. **O julgamento nunca vira código, e o código nunca vira
julgamento.**

---

## Instalação

Requer **Python 3.12** e usa **exclusivamente o `.venv` da raiz do repositório**. Nunca crie
outro ambiente virtual — é regra do `CLAUDE.md`.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e .
```

---

## Uso

### 1. Coletar (Fase A)

```powershell
.venv\Scripts\python.exe -m magalu_releases coletar --n 3
```

`--n` é a única entrada de usuário. Qualquer valor funciona — não há `N` fixo no código.

Cria `runs/magalu_N3_<períodos>_<timestamp>/` com `pdfs/`, `paginas/`, `documentos.json`,
`manifesto.json` e **`dossie.md`**.

### 2. Analisar (Fase B — agente)

Abra o `dossie.md` e siga a skill **`magalu-release-analysis`**. O dossiê traz o texto página
a página e o contrato de saída. Grave `fatos.json` no mesmo diretório.

### 3. Validar o portão

```powershell
.venv\Scripts\python.exe -m magalu_releases validar-fatos --run runs\<run_id>
```

Lista **todas** as violações de contrato de uma vez. Só passa quando o arquivo está íntegro.

### 4. Relatar (Fase C)

```powershell
.venv\Scripts\python.exe -m magalu_releases relatar --run runs\<run_id>
```

Gera `analise_<run_id>.xlsx`, `dashboard_<run_id>.html`, `resumo.md` e `auditoria.json`. Sai
com código diferente de zero quando a auditoria encontra falha de severidade alta — a execução
não pode ser apresentada como concluída nesse caso.

---

## A planilha

| Aba | Uma linha por | Serve para |
|---|---|---|
| **Resumo** | bloco | escopo da execução (N pedido × N obtido) e resumo executivo |
| **Comparativo** | série | uma coluna por período, em ordem crescente, mais variações |
| **Evidências** | fato | documento, página, trecho literal, unidade, confiança |
| **Documentos** | PDF | URL oficial, SHA-256, páginas, textual sim/não |
| **Pendências** | item de revisão | conflitos, ambiguidades, lacunas |
| **Auditoria** | verificação | inclusive as que passaram |

De qualquer número exibido é possível chegar a uma linha de **Evidências**.

A planilha **não tem fórmulas vivas**: é registro auditável, não modelo recalculável. Uma
fórmula que recalcula pode divergir do que foi extraído e auditado.

---

## O dashboard

`dashboard_<run_id>.html` — **uma página, um arquivo, nada externo**. Sem CDN, sem fonte
remota, sem script de terceiro: abre offline, hoje e daqui a um ano.

É gerado **a partir da planilha já gravada**, não dos objetos em memória. A página só pode
mostrar o que está no arquivo entregue, e qualquer execução antiga pode ser re-renderizada a
partir do próprio artefato.

Traz escopo, comparativo por série com mini-gráficos, documentos com SHA-256, pendências e a
auditoria inteira — inclusive o que passou. Cada linha do comparativo abre a evidência que a
sustenta: documento, página e trecho literal. Ausência aparece como `—`, nunca como zero, e a
variação suprimida mostra o motivo.

---

## Regras que o código impõe

- Ausência é `null` — nunca `0`, nunca `"-"`.
- `valor_original` é preservado literalmente e gravado **como texto** (o Excel reinterpreta
  `9.856,4` conforme o locale de quem abrir).
- Unidade ambígua ⇒ `valor_normalizado` nulo. Número certo em unidade errada é pior que
  número ausente.
- Séries são separadas pela tupla `(métrica, segmento, base, periodicidade, tipo_valor)`.
  Ajustado nunca cai na série do reportado.
- Margens variam em **pontos percentuais**; valores monetários, em **%** e absoluto.
- Variação não é calculada com denominador zero, ponta ausente ou confiança baixa.
- Ordenação é sempre por **período fiscal** — o release do 4T é publicado no ano seguinte.

---

## Testes

```powershell
.venv\Scripts\python.exe -m pytest
```

**512 testes, nenhum toca a rede.** A concentração é deliberada em `numeros`, `periodos`,
`series` e `variacoes`: é onde um erro passa despercebido até chegar na planilha.
`tests/test_integracao.py` exercita a Fase C ponta a ponta.

---

## Estrutura

```
config/settings.toml          ponto único de configuração (URL, cabeçalhos, limiares)
src/magalu_releases/
  ├── config.py numeros.py periodos.py models.py vocabularios.py
  ├── fonte/       http · descoberta · classificacao · selecao · download
  ├── extracao/    texto · dossie
  ├── fatos/       esquema (o portão)
  ├── analise/     series · variacoes
  ├── saida/       excel · dashboard · resumo · pendencias
  ├── auditoria/   checks
  └── cli.py
tests/                        512 testes + fixtures sintéticas
runs/                         artefatos por execução (não versionado)
.claude/skills/magalu-release-analysis/   o procedimento de análise
CLAUDE.md                     regras permanentes do repositório
```

---

## Notas de operação

**O site de RI fica atrás do WAF da Azion.** Ele recusa clientes sem o conjunto completo de
cabeçalhos de navegador e aplica *rate limiting* por IP. O cliente HTTP já trata isso:
cabeçalhos completos, sessão com cookies, intervalo entre requisições e backoff exponencial.
Em janela de bloqueio, a coleta falha alto em vez de insistir — os parâmetros estão em
`config/settings.toml`.

**Sem OCR.** PDF digitalizado não é processado e vira pendência.

**Paginação da Central.** A listagem pagina por `__doPostBack`. Para `N` grande, períodos
antigos podem não estar na primeira página; a coleta avisa quando detecta paginação.
