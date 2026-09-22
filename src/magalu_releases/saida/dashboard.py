"""Dashboard HTML — a entrega em forma de página.

Lê a **planilha já gravada**, nunca os objetos em memória. Isso mantém a página
honesta por construção: ela só pode mostrar o que está no arquivo entregue, e
uma execução antiga pode ser re-renderizada a partir do próprio artefato.

Três decisões que parecem estética e não são:

- **Um arquivo, nada externo.** CSS e SVG inline, sem CDN e sem fonte remota. Um
  relatório que precisa de internet para renderizar deixa de ser auditável
  justamente quando alguém o abre meses depois.
- **Todo número leva à evidência.** Cada linha do comparativo abre documento,
  página e trecho literal, como na aba Evidências. Número sem rastro na tela é o
  mesmo problema que número sem rastro na planilha.
- **Ausência aparece como ausência.** Posição vazia é `—`, nunca `0`, e a
  variação suprimida mostra o motivo.

As cores seguem a paleta validada da skill de visualização: azul para valores
positivos, vermelho para negativos (par divergente, aprovado nos dois modos pelo
validador), e a paleta de status para a auditoria, sempre com rótulo textual ao
lado — cor nunca carrega significado sozinha.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from magalu_releases.auditoria.checks import verificacao
from magalu_releases.models import VerificacaoAuditoria
from magalu_releases.vocabularios import Severidade

_CHECK_DASHBOARD = (
    "dsh_completo",
    "Dashboard traz os N períodos, todas as séries e as pendências",
)


@dataclass(frozen=True, slots=True)
class _Conteudo:
    resumo: list[tuple[str, str]]
    series: list[dict]
    periodos: list[str]
    evidencias: list[dict]
    documentos: list[dict]
    pendencias: list[dict]
    auditoria: list[dict]
    texto_resumo: list[str]


def _linhas(aba) -> list[dict]:
    cabecalhos = [c.value for c in aba[1]]
    saida = []
    for linha in range(2, aba.max_row + 1):
        registro = {
            nome: aba.cell(row=linha, column=indice + 1).value
            for indice, nome in enumerate(cabecalhos)
            if nome
        }
        if any(v is not None for v in registro.values()):
            saida.append(registro)
    return saida


def _parece_periodo(texto: str) -> bool:
    import re

    return bool(re.fullmatch(r"[1-4]T\d{2,4}|\d{4}-(?:Q[1-4]|\d{1,2}M|FY)", texto.strip()))


def _ler(caminho: Path) -> _Conteudo:
    wb = load_workbook(caminho)

    aba_resumo = wb["Resumo"]
    cabecalho, texto_resumo = [], []
    for linha in range(1, aba_resumo.max_row + 1):
        rotulo = aba_resumo.cell(row=linha, column=1).value
        valor = aba_resumo.cell(row=linha, column=2).value
        if rotulo and valor is not None:
            cabecalho.append((str(rotulo), str(valor)))
        elif rotulo:
            texto_resumo.append(str(rotulo))

    comparativo = wb["Comparativo"]
    periodos = [
        str(c.value) for c in comparativo[1] if c.value and _parece_periodo(str(c.value))
    ]

    return _Conteudo(
        resumo=cabecalho,
        series=_linhas(comparativo),
        periodos=periodos,
        evidencias=_linhas(wb["Evidências"]),
        documentos=_linhas(wb["Documentos"]),
        pendencias=[p for p in _linhas(wb["Pendências"]) if p.get("tipo")],
        auditoria=_linhas(wb["Auditoria"]),
        texto_resumo=texto_resumo,
    )


def _e(valor) -> str:
    """Escapa para HTML. Texto de documento entra como texto, jamais como marcação."""
    return _html.escape("" if valor is None else str(valor), quote=True)


def _numero(valor) -> str:
    """Formato brasileiro. `None` é ausência declarada, nunca zero."""
    if valor is None or valor == "":
        return "—"
    if not isinstance(valor, (int, float)):
        return _e(valor)
    inteiro = abs(valor - round(valor)) < 1e-9
    texto = f"{valor:,.0f}" if inteiro else f"{valor:,.1f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _variacao(serie: dict) -> tuple[str, str]:
    """Devolve (texto, sentido). Percentual varia em p.p.; o resto, em %."""
    if serie.get("variacao_pp") is not None:
        valor = serie["variacao_pp"]
        return f"{_numero(valor)} p.p.", _sentido(valor)
    if serie.get("variacao_pct") is not None:
        valor = serie["variacao_pct"]
        return f"{_numero(valor)}%", _sentido(valor)
    if serie.get("variacao_abs") is not None:
        valor = serie["variacao_abs"]
        return _numero(valor), _sentido(valor)
    return "não calculada", "neutro"


def _sentido(valor) -> str:
    if valor is None or abs(valor) < 1e-9:
        return "neutro"
    return "positivo" if valor > 0 else "negativo"


def _colunas_grafico(serie: dict, periodos: list[str]) -> str:
    """Mini-colunas SVG: uma por período, escala própria da série.

    Escala por série, e nunca dois eixos no mesmo desenho: receita em bilhões e
    margem em porcento não compartilham régua. O zero é linha de base visível
    quando a série tem valor negativo.
    """
    valores = [serie.get(p) for p in periodos]
    presentes = [v for v in valores if isinstance(v, (int, float))]
    if not presentes:
        return '<div class="sem-grafico">sem valor para desenhar</div>'

    topo = max(presentes + [0])
    base = min(presentes + [0])
    intervalo = (topo - base) or 1
    largura, altura, folga = 168, 48, 4
    passo = largura / max(len(periodos), 1)
    zero = altura - ((0 - base) / intervalo) * (altura - folga)

    partes = [
        f'<svg class="mini" viewBox="0 0 {largura} {altura}" role="img" '
        f'aria-label="valores por período">'
    ]
    partes.append(
        f'<line x1="0" y1="{zero:.1f}" x2="{largura}" y2="{zero:.1f}" class="base"/>'
    )
    for indice, (rotulo, valor) in enumerate(zip(periodos, valores)):
        if not isinstance(valor, (int, float)):
            continue
        y = altura - ((valor - base) / intervalo) * (altura - folga)
        topo_barra, alto = (y, zero - y) if valor >= 0 else (zero, y - zero)
        classe = "pos" if valor >= 0 else "neg"
        # 2px de respiro entre barras vizinhas, cantos arredondados na ponta.
        partes.append(
            f'<rect class="barra {classe}" x="{indice * passo + 3:.1f}" '
            f'y="{topo_barra:.1f}" width="{passo - 6:.1f}" '
            f'height="{max(abs(alto), 1.5):.1f}" rx="2">'
            f"<title>{_e(rotulo)}: {_numero(valor)}</title></rect>"
        )
    partes.append("</svg>")
    return "".join(partes)


_STATUS = {
    "PASS": ("good", "✓", "passou"),
    "FAIL": ("critical", "✗", "falhou"),
    "ALERTA": ("warning", "!", "alerta"),
}


def _severidade_classe(valor: str) -> str:
    return {
        Severidade.ALTA.value: "critical",
        Severidade.MEDIA.value: "warning",
        Severidade.BAIXA.value: "neutro",
    }.get(str(valor), "neutro")


def gerar_dashboard(*, caminho_xlsx: Path | str, destino: Path | str, run_id: str,
                    fonte: str) -> Path:
    """Renderiza o dashboard a partir da planilha e devolve o caminho gravado."""
    conteudo = _ler(Path(caminho_xlsx))
    alvo = Path(destino)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(_pagina(conteudo, run_id=run_id, fonte=fonte), encoding="utf-8")
    return alvo


def validar_dashboard(caminho: Path | str, *, n_periodos: int, series_ids,
                      rotulos=()) -> tuple[VerificacaoAuditoria, ...]:
    """Relê o HTML gravado e confere que a entrega chegou inteira à página."""
    check_id, descricao = _CHECK_DASHBOARD
    alvo = Path(caminho)
    if not alvo.is_file():
        return (
            verificacao(check_id, descricao, "dashboard gravado",
                        f"arquivo não encontrado: {alvo}", False, Severidade.MEDIA),
        )

    html = alvo.read_text(encoding="utf-8")
    faltando = [s for s in series_ids if s and str(s) not in html]
    periodos_faltando = [r for r in rotulos if str(r) not in html]

    detalhes = []
    if faltando:
        detalhes.append("séries ausentes: " + ", ".join(str(s) for s in faltando[:10]))
    if periodos_faltando:
        detalhes.append("períodos ausentes: " + ", ".join(str(r) for r in periodos_faltando))
    if "Pendências" not in html:
        detalhes.append("seção de pendências ausente")

    return (
        verificacao(
            check_id,
            descricao,
            f"{len(list(series_ids))} série(s) e {n_periodos} período(s) na página",
            "completo" if not detalhes else f"{len(detalhes)} lacuna(s)",
            not detalhes,
            Severidade.MEDIA,
            "; ".join(detalhes),
        ),
    )


# --- Renderização ------------------------------------------------------------

_ESTILO = """
:root {
  color-scheme: light;
  --surface: #fcfcfb; --plano: #f9f9f7; --tinta: #0b0b0b; --tinta-2: #52514e;
  --mudo: #898781; --grade: #e1e0d9; --linha: #c3c2b7; --borda: rgba(11,11,11,.10);
  --pos: #2a78d6; --neg: #e34948;
  --good: #0ca30c; --warning: #fab219; --critical: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #1a1a19; --plano: #0d0d0d; --tinta: #fff; --tinta-2: #c3c2b7;
    --mudo: #898781; --grade: #2c2c2a; --linha: #383835; --borda: rgba(255,255,255,.10);
    --pos: #3987e5; --neg: #e66767;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --plano: #0d0d0d; --tinta: #fff; --tinta-2: #c3c2b7;
  --mudo: #898781; --grade: #2c2c2a; --linha: #383835; --borda: rgba(255,255,255,.10);
  --pos: #3987e5; --neg: #e66767;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 16px 72px; background: var(--plano); color: var(--tinta);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
.pagina { max-width: 1180px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 40px 0 12px; }
.sub { color: var(--tinta-2); margin: 0 0 4px; }
.mudo { color: var(--mudo); font-size: 13px; }
nav { display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0 0; font-size: 14px; }
nav a { color: var(--tinta-2); }
.cartoes { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); margin-top: 20px; }
.cartao { background: var(--surface); border: 1px solid var(--borda); border-radius: 10px; padding: 14px 16px; }
.cartao .rotulo { color: var(--tinta-2); font-size: 13px; }
.cartao .valor { font-size: 28px; margin: 6px 0 2px; }
.cartao .unidade { color: var(--mudo); font-size: 13px; }
.delta { font-size: 13px; font-variant-numeric: tabular-nums; }
.positivo { color: var(--pos); } .negativo { color: var(--neg); } .neutro { color: var(--mudo); }
table { width: 100%; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--borda); border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--grade); vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--tinta-2); font-weight: 600; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:last-child td { border-bottom: 0; }
.mini { width: 168px; height: 48px; display: block; }
.mini .base { stroke: var(--linha); stroke-width: 1; }
.mini .barra.pos { fill: var(--pos); } .mini .barra.neg { fill: var(--neg); }
.sem-grafico { color: var(--mudo); font-size: 12px; }
details { background: var(--surface); }
details summary { cursor: pointer; color: var(--tinta-2); font-size: 13px; padding: 2px 0; }
.evidencia { margin: 8px 0 4px; padding: 10px 12px; background: var(--plano);
  border-left: 3px solid var(--linha); border-radius: 4px; }
.trecho { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
  white-space: pre-wrap; color: var(--tinta); margin: 4px 0 0; }
.etiqueta { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.ponto { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.ponto.good { background: var(--good); } .ponto.warning { background: var(--warning); }
.ponto.critical { background: var(--critical); } .ponto.neutro { background: var(--mudo); }
.aviso { border-left: 3px solid var(--critical); padding: 10px 14px; background: var(--surface);
  border-radius: 6px; margin: 16px 0; }
.nota { color: var(--tinta-2); font-size: 13.5px; }
footer { margin-top: 48px; color: var(--mudo); font-size: 12.5px; }
@media (max-width: 720px) {
  .mini { width: 120px; }
  th, td { padding: 8px; }
}
"""


def _cartoes(conteudo: _Conteudo) -> str:
    """Tiles das séries de maior porte: valor do período mais recente e variação."""
    destaque = [
        s for s in conteudo.series
        if s.get("metrica_id") in {"receita_liquida", "ebitda_ajustado", "lucro_liquido",
                                   "margem_bruta", "vendas_totais"}
        and s.get("base") in {"reportado", "ajustado"}
    ][:5] or conteudo.series[:4]

    partes = []
    ultimo = conteudo.periodos[-1] if conteudo.periodos else None
    for serie in destaque:
        valor = serie.get(ultimo) if ultimo else None
        texto, sentido = _variacao(serie)
        partes.append(
            f'<div class="cartao">'
            f'<div class="rotulo">{_e(serie.get("metrica_rotulo"))}</div>'
            f'<div class="valor">{_numero(valor)}</div>'
            f'<div class="unidade">{_e(serie.get("unidade_serie") or "unidade não determinada")}'
            f' · {_e(ultimo)}</div>'
            f'<div class="delta {sentido}">{_e(texto)} '
            f'<span class="mudo">vs. período anterior</span></div>'
            f"</div>"
        )
    return f'<div class="cartoes">{"".join(partes)}</div>'


def _tabela_series(conteudo: _Conteudo, evidencias_por_serie: dict) -> str:
    colunas = "".join(f'<th class="num">{_e(p)}</th>' for p in conteudo.periodos)
    linhas = []
    for serie in conteudo.series:
        celulas = "".join(
            f'<td class="num">{_numero(serie.get(p))}</td>' for p in conteudo.periodos
        )
        texto, sentido = _variacao(serie)
        motivo = serie.get("motivo_nao_calculada")
        nota = f'<div class="mudo">{_e(motivo)}</div>' if motivo else ""
        linhas.append(
            f"<tr><td>{_e(serie.get('metrica_rotulo'))}"
            f'<div class="mudo">{_e(serie.get("serie_id"))}</div>'
            f"{_evidencias_da_serie(evidencias_por_serie.get(serie.get('serie_id'), []))}</td>"
            f"<td>{_e(serie.get('base'))}<div class=\"mudo\">{_e(serie.get('segmento'))}</div></td>"
            f"<td>{_e(serie.get('unidade_serie') or '—')}</td>"
            f"<td>{_colunas_grafico(serie, conteudo.periodos)}</td>"
            f"{celulas}"
            f'<td class="num {sentido}">{_e(texto)}{nota}</td></tr>'
        )
    return (
        "<table><thead><tr><th>Série</th><th>Base</th><th>Unidade</th><th>Períodos</th>"
        f"{colunas}<th class=\"num\">Variação</th></tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody></table>"
    )


def _evidencias_da_serie(evidencias: list[dict]) -> str:
    if not evidencias:
        return '<div class="mudo">sem evidência associada</div>'
    blocos = []
    for e in evidencias:
        blocos.append(
            f'<div class="evidencia">'
            f'<div class="mudo">{_e(e.get("periodo_rotulo"))} · {_e(e.get("documento_id"))}'
            f' · página {_e(e.get("pagina"))} · confiança {_e(e.get("confianca"))}</div>'
            f'<div><strong>{_e(e.get("valor_original"))}</strong> '
            f'<span class="mudo">{_e(e.get("unidade") or "unidade não determinada")}</span></div>'
            f'<p class="trecho">{_e(e.get("trecho_fonte"))}</p>'
            f"</div>"
        )
    return (
        f"<details><summary>evidência ({len(evidencias)})</summary>"
        f"{''.join(blocos)}</details>"
    )


def _tabela_documentos(conteudo: _Conteudo) -> str:
    linhas = []
    for d in conteudo.documentos:
        linhas.append(
            f"<tr><td>{_e(d.get('periodo_rotulo'))}</td>"
            f"<td>{_e(d.get('titulo'))}<div class=\"mudo\">{_e(d.get('documento_id'))}</div></td>"
            f"<td>{_e(d.get('nome_servidor') or '—')}</td>"
            f"<td class=\"num\">{_e(d.get('paginas'))}</td>"
            f'<td class="trecho">{_e(d.get("sha256"))}</td>'
            f"<td>{_e(d.get('motivo_descarte') or '—')}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Período</th><th>Documento</th><th>Nome no servidor</th>"
        '<th class="num">Páginas</th><th>SHA-256</th><th>Descarte</th></tr></thead>'
        f"<tbody>{''.join(linhas)}</tbody></table>"
    )


def _tabela_pendencias(conteudo: _Conteudo) -> str:
    if not conteudo.pendencias:
        return '<p class="nota">Nenhuma pendência registrada nesta execução.</p>'
    linhas = []
    for p in conteudo.pendencias:
        classe = _severidade_classe(p.get("severidade"))
        linhas.append(
            f"<tr><td>{_e(p.get('pendencia_id'))}</td>"
            f'<td><span class="etiqueta"><span class="ponto {classe}"></span>'
            f"{_e(p.get('severidade'))}</span></td>"
            f"<td>{_e(p.get('tipo'))}</td><td>{_e(p.get('descricao'))}"
            f"<div class=\"mudo\">{_e(p.get('acao_sugerida'))}</div></td></tr>"
        )
    return (
        "<table><thead><tr><th>ID</th><th>Severidade</th><th>Tipo</th>"
        f"<th>Descrição e ação</th></tr></thead><tbody>{''.join(linhas)}</tbody></table>"
    )


def _tabela_auditoria(conteudo: _Conteudo) -> str:
    linhas = []
    for v in conteudo.auditoria:
        classe, simbolo, rotulo = _STATUS.get(str(v.get("resultado")), ("neutro", "·", "—"))
        linhas.append(
            f"<tr><td>{_e(v.get('check_id'))}</td>"
            f'<td><span class="etiqueta"><span class="ponto {classe}"></span>'
            f"{simbolo} {_e(rotulo)}</span></td>"
            f"<td>{_e(v.get('descricao'))}</td>"
            f"<td>{_e(v.get('esperado'))}</td><td>{_e(v.get('obtido'))}"
            f"<div class=\"mudo\">{_e(v.get('detalhe') or '')}</div></td></tr>"
        )
    return (
        "<table><thead><tr><th>Check</th><th>Resultado</th><th>Verifica</th>"
        f"<th>Esperado</th><th>Obtido</th></tr></thead><tbody>{''.join(linhas)}</tbody></table>"
    )


def _pagina(conteudo: _Conteudo, *, run_id: str, fonte: str) -> str:
    contagem = {"PASS": 0, "FAIL": 0, "ALERTA": 0}
    for v in conteudo.auditoria:
        chave = str(v.get("resultado"))
        if chave in contagem:
            contagem[chave] += 1

    evidencias_por_serie: dict[str, list[dict]] = {}
    for e in conteudo.evidencias:
        chave = "-".join(
            str(e.get(c) or "")
            for c in ("metrica_id", "segmento", "base", "periodicidade", "tipo_valor")
        )
        evidencias_por_serie.setdefault(chave, []).append(e)

    cabecalho = "".join(
        f"<tr><td>{_e(r)}</td><td>{_e(v)}</td></tr>" for r, v in conteudo.resumo
    )
    falhas = contagem["FAIL"]
    aviso = (
        f'<div class="aviso"><strong>{falhas} verificação(ões) de auditoria falharam.</strong> '
        "A execução não pode ser apresentada como concluída enquanto houver falha de "
        "severidade alta.</div>"
        if falhas
        else ""
    )
    resumo_texto = "".join(f"<p class=\"nota\">{_e(l)}</p>" for l in conteudo.texto_resumo)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Análise de releases — Magazine Luiza</title>
<style>{_ESTILO}</style>
</head>
<body>
<div class="pagina">
<header>
  <h1>Análise de releases de resultados — Magazine Luiza</h1>
  <p class="sub">{_e(fonte)}</p>
  <p class="mudo">Execução {_e(run_id)} · página gerada em
     {datetime.now().strftime("%d/%m/%Y %H:%M")} a partir da planilha desta execução</p>
  <p class="nota">Conteúdo descritivo, comparativo e rastreável, limitado ao que os
     documentos reportam. Não constitui aconselhamento de investimento.</p>
  <nav>
    <a href="#escopo">Escopo</a><a href="#comparativo">Comparativo</a>
    <a href="#documentos">Documentos</a><a href="#pendencias">Pendências</a>
    <a href="#auditoria">Auditoria</a>
  </nav>
</header>

{aviso}

<section id="escopo">
  <h2>Escopo da execução</h2>
  <table><tbody>{cabecalho}</tbody></table>
  {_cartoes(conteudo)}
</section>

<section id="comparativo">
  <h2>Comparativo por série</h2>
  <p class="mudo">Períodos em ordem cronológica crescente. Ausência aparece como —,
     nunca como zero. Margens variam em pontos percentuais; valores monetários, em
     porcentagem. Cada linha abre a evidência que a sustenta.</p>
  {_tabela_series(conteudo, evidencias_por_serie)}
</section>

<section id="documentos">
  <h2>Documentos analisados</h2>
  {_tabela_documentos(conteudo)}
</section>

<section id="pendencias">
  <h2>Pendências</h2>
  {_tabela_pendencias(conteudo)}
</section>

<section id="auditoria">
  <h2>Auditoria</h2>
  <p class="mudo">{contagem["PASS"]} PASS · {contagem["FAIL"]} FAIL ·
     {contagem["ALERTA"]} ALERTA — inclusive as verificações que passaram.</p>
  {_tabela_auditoria(conteudo)}
</section>

<section id="resumo">
  <h2>Resumo executivo</h2>
  {resumo_texto}
</section>

<footer>
  Gerado a partir de {_e(Path(run_id).name)}. Os valores são os do documento de origem;
  o texto original de cada número está na evidência.
</footer>
</div>
</body>
</html>
"""
