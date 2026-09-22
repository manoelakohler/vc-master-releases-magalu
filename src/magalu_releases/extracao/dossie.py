"""Montagem do dossiê — o pacote que a fase de análise lê.

O dossiê carrega o material bruto (texto página a página, com o documento e o
período amarrados) e o contrato que a saída precisa cumprir. Ele **não** repete
o procedimento de análise: isso vive na skill `magalu-release-analysis`, que é a
fonte de verdade. Duplicar aqui garantiria divergência na primeira atualização.

O nome da execução carrega empresa, N, períodos e momento, de modo que uma
execução nunca sobrescreva silenciosamente a anterior.
"""

from __future__ import annotations

import re
from datetime import datetime

_NAO_ALFANUM = re.compile(r"[^A-Za-z0-9]+")

_CONTRATO = """\
## Contrato de saída — `fatos.json`

Grave neste diretório um `fatos.json` com a forma:

```json
{
  "run_id": "<run_id desta execução>",
  "fatos": [
    {
      "fato_id": "f-0001",
      "metrica_id": "receita_liquida",
      "metrica_rotulo": "<rótulo literal do documento>",
      "segmento": "consolidado | lojas_fisicas | ecommerce | marketplace | 1p | 3p | servicos | outro",
      "base": "reportado | ajustado | indefinido",
      "periodicidade": "trimestre | acumulado | anual",
      "tipo_valor": "absoluto | percentual | variacao_abs | variacao_pct | variacao_pp | texto",
      "periodo_rotulo": "2T25",
      "valor_original": "<exatamente como aparece, sem limpeza>",
      "valor_normalizado": 9856.4,
      "unidade": "R$ milhões",
      "documento_id": "<id da lista acima>",
      "pagina": 7,
      "trecho_fonte": "<trecho literal que CONTÉM valor_original>",
      "confianca": "alta | media | baixa",
      "flags": [],
      "revisao_humana": false,
      "motivo": null
    }
  ]
}
```

Invariantes que o validador recusa:

- `trecho_fonte` precisa **conter** `valor_original`, senão a evidência não sustenta o valor.
- `unidade` nula exige `valor_normalizado` nulo — nunca `0`.
- `revisao_humana` precisa espelhar a presença de `flags`.
- `confianca: "baixa"` e `base: "indefinido"` implicam `revisao_humana: true`.

Valide com:

```
.venv\\Scripts\\python.exe -m magalu_releases validar-fatos --run <diretório desta execução>
```
"""


def nome_execucao(*, n: int, periodos, momento: str | None = None) -> str:
    """Identificador da execução: empresa, N, períodos e momento."""
    carimbo = momento or datetime.now().strftime("%Y%m%d-%H%M%S")
    periodos = tuple(periodos)
    if periodos:
        faixa = periodos[0] if len(periodos) == 1 else f"{periodos[0]}_a_{periodos[-1]}"
    else:
        faixa = "sem-periodo"
    faixa = _NAO_ALFANUM.sub("-", faixa).strip("-")
    return f"magalu_N{n}_{faixa}_{carimbo}"


def montar_dossie(*, run_id: str, n_pedido: int, documentos, paginas_por_documento) -> str:
    """Monta o texto do dossiê em Markdown."""
    linhas: list[str] = []
    linhas.append(f"# Dossiê de análise — {run_id}")
    linhas.append("")
    linhas.append(
        "Siga a skill **`magalu-release-analysis`** para conduzir a extração. "
        "Este arquivo traz o material e o contrato; o procedimento está na skill."
    )
    linhas.append("")
    linhas.append(f"- Releases pedidos: **{n_pedido}**")
    linhas.append(f"- Documentos neste dossiê: **{len(documentos)}**")
    linhas.append("")

    linhas.append("## Documentos")
    linhas.append("")
    linhas.append("| documento_id | período | título | páginas | sha256 |")
    linhas.append("|---|---|---|---|---|")
    for d in documentos:
        periodo = d.periodo.rotulo if d.periodo else "—"
        sha = (d.sha256 or "")[:12]
        linhas.append(
            f"| `{d.documento_id}` | {periodo} | {d.titulo} | {d.paginas or '—'} | `{sha}` |"
        )
    linhas.append("")

    linhas.append(_CONTRATO)
    linhas.append("")

    linhas.append("## Texto extraído")
    linhas.append("")
    for d in documentos:
        periodo = d.periodo.rotulo if d.periodo else "período indeterminado"
        linhas.append(f"### `{d.documento_id}` — {d.titulo} ({periodo})")
        linhas.append("")
        for pagina in paginas_por_documento.get(d.documento_id, []):
            marca = ""
            if pagina.tabela_suspeita:
                marca = (
                    "  \n> **Estrutura de tabela não confirmada nesta página** — "
                    f"{pagina.observacao}. Não deduza o alinhamento das colunas: "
                    "na dúvida, registre `null` com pendência."
                )
            linhas.append(f"#### Página {pagina.pagina} ({pagina.caracteres} caracteres){marca}")
            linhas.append("")
            linhas.append("```text")
            linhas.append(pagina.texto)
            linhas.append("```")
            linhas.append("")

    return "\n".join(linhas)
