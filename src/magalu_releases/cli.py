"""Interface de execução.

O fluxo tem duas fases separadas por um portão, porque o julgamento não vira
código (regra do CLAUDE.md) e o código não vira julgamento:

    coletar --n N      → Python determinístico: descobre, seleciona, baixa, extrai
    (portão)           → a análise lê o dossiê e grava fatos.json, guiada pela skill
    validar-fatos      → o portão confere o contrato
    relatar            → Python determinístico: séries, variações, Excel, auditoria

A única entrada de usuário é **N**. Tudo mais é configuração.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from magalu_releases.analise.series import construir_series
from magalu_releases.analise.variacoes import calcular_variacoes
from magalu_releases.auditoria.checks import auditar
from magalu_releases.config import carregar_config
from magalu_releases.extracao.dossie import montar_dossie, nome_execucao
from magalu_releases.extracao.texto import PdfIlegivel, extrair_paginas
from magalu_releases.fatos.esquema import FatosInvalidos, carregar_fatos
from magalu_releases.fonte.classificacao import classificar_documento  # noqa: F401
from magalu_releases.fonte.descoberta import descobrir_documentos, tem_paginacao
from magalu_releases.fonte.download import baixar_documento, validar_pdf_textual
from magalu_releases.fonte.http import ClienteHttp, FalhaHttp
from magalu_releases.fonte.selecao import selecionar_releases
from magalu_releases.models import Documento
from magalu_releases.saida.excel import gerar_excel, validar_planilha
from magalu_releases.saida.pendencias import consolidar_pendencias
from magalu_releases.saida.resumo import montar_esqueleto, validar_resumo
from magalu_releases.vocabularios import ResultadoCheck


def _n_positivo(texto: str) -> int:
    valor = int(texto)
    if valor < 1:
        raise argparse.ArgumentTypeError(f"N precisa ser >= 1, recebido {valor}")
    return valor


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magalu_releases",
        description="Análise de releases de resultados da Magazine Luiza.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    coletar = sub.add_parser("coletar", help="Fase A: descobre, baixa e extrai texto")
    coletar.add_argument("--n", type=_n_positivo, required=True,
                         help="quantidade de releases mais recentes a analisar")

    validar = sub.add_parser("validar-fatos", help="Portão: confere fatos.json contra o contrato")
    validar.add_argument("--run", required=True, help="diretório da execução")

    relatar = sub.add_parser("relatar", help="Fase C: séries, variações, Excel e auditoria")
    relatar.add_argument("--run", required=True, help="diretório da execução")

    return parser


def _serializar(objeto):
    if hasattr(objeto, "canonico"):
        return {"canonico": objeto.canonico, "rotulo": objeto.rotulo}
    if hasattr(objeto, "value"):
        return objeto.value
    if hasattr(objeto, "__dataclass_fields__"):
        return asdict(objeto)
    return str(objeto)


def comando_coletar(n: int, *, cfg=None, cliente=None, raiz=None) -> int:
    cfg = cfg or carregar_config()
    cliente = cliente or ClienteHttp(cfg.http)
    raiz = Path(raiz) if raiz else Path(cfg.execucao.diretorio_execucoes)

    print(f"Fonte: {cfg.fonte.url_central}")
    try:
        pagina = cliente.obter(cfg.fonte.url_central, referer=cfg.fonte.base_url)
    except FalhaHttp as erro:
        print(f"ERRO ao acessar a Central de Resultados: {erro}")
        print("A coleta não continua com fonte não oficial nem com dado de outra origem.")
        return 2

    html = pagina.conteudo.decode("utf-8", "replace")
    descobertos = descobrir_documentos(html, base_url=cfg.fonte.base_url)
    print(f"Documentos encontrados na Central: {len(descobertos)}")
    if tem_paginacao(html):
        print("AVISO: a Central tem paginação por postback; "
              "para N grande, períodos antigos podem não estar nesta página.")

    documentos = [
        Documento(
            documento_id=d.documento_id,
            titulo=d.titulo,
            tipo=d.tipo,
            periodo=d.periodo,
            url_origem=d.url_origem,
        )
        for d in descobertos
    ]

    selecao = selecionar_releases(documentos, n)
    print(f"Releases selecionados: {selecao.n_obtido} de {selecao.n_pedido} pedidos")
    if selecao.faltou_documento:
        print(f"AVISO: foram pedidos {selecao.n_pedido} releases e localizados {selecao.n_obtido}.")

    run_id = nome_execucao(n=n, periodos=selecao.periodos)
    execucao = raiz / run_id
    (execucao / "pdfs").mkdir(parents=True, exist_ok=True)

    baixados = []
    paginas_por_documento = {}
    pendencias = list(selecao.pendencias)

    for documento in selecao.selecionados:
        print(f"  baixando {documento.documento_id} ({documento.periodo.rotulo})...")
        try:
            baixado = baixar_documento(cliente, documento, execucao / "pdfs")
        except Exception as erro:
            print(f"    FALHA: {erro}")
            continue

        try:
            paginas = extrair_paginas(
                execucao / "pdfs" / baixado.arquivo_local, documento_id=baixado.documento_id
            )
        except PdfIlegivel as erro:
            print(f"    PDF ilegível: {erro}")
            continue

        textual = validar_pdf_textual(
            [p.texto for p in paginas],
            minimo_caracteres=cfg.pdf.minimo_caracteres_por_pagina,
            proporcao_minima=cfg.pdf.minimo_paginas_textuais_proporcao,
        )
        from dataclasses import replace

        baixado = replace(baixado, paginas=len(paginas), textual=textual.textual)
        if not textual.textual:
            print(f"    NÃO TEXTUAL: {textual.motivo} — sem OCR, vira pendência")
            baixados.append(replace(baixado, motivo_descarte=textual.motivo))
            continue

        baixados.append(baixado)
        paginas_por_documento[baixado.documento_id] = paginas

    (execucao / "documentos.json").write_text(
        json.dumps([asdict(d) for d in baixados], default=_serializar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (execucao / "paginas").mkdir(exist_ok=True)
    for documento_id, paginas in paginas_por_documento.items():
        (execucao / "paginas" / f"{documento_id}.json").write_text(
            json.dumps([asdict(p) for p in paginas], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    dossie = montar_dossie(
        run_id=run_id, n_pedido=n, documentos=baixados,
        paginas_por_documento=paginas_por_documento,
    )
    (execucao / "dossie.md").write_text(dossie, encoding="utf-8")
    (execucao / "manifesto.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "n_pedido": selecao.n_pedido,
                "n_obtido": selecao.n_obtido,
                "periodos": list(selecao.periodos),
                "fonte": cfg.fonte.url_central,
                "pendencias": [asdict(p) for p in consolidar_pendencias(pendencias)],
            },
            default=_serializar,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nExecução gravada em: {execucao}")
    print("Próximo passo (fase de análise, guiada pela skill magalu-release-analysis):")
    print(f"  1. ler {execucao / 'dossie.md'}")
    print(f"  2. gravar {execucao / 'fatos.json'}")
    print(f"  3. rodar: validar-fatos --run {execucao}")
    return 0


def comando_validar_fatos(diretorio: str) -> int:
    execucao = Path(diretorio)
    caminho = execucao / "fatos.json"
    if not caminho.is_file():
        print(f"ERRO: fatos.json não encontrado em {execucao}")
        print("A fase de análise precisa gravar esse arquivo antes de relatar.")
        return 2

    try:
        resultado = carregar_fatos(caminho, estrito=False)
    except FatosInvalidos as erro:
        print(f"ERRO: {erro}")
        return 2

    print(f"Fatos carregados: {len(resultado.fatos)}")
    if resultado.problemas:
        print(f"\n{len(resultado.problemas)} violação(ões) do contrato:")
        for problema in resultado.problemas:
            print(f"  - {problema}")
        return 1

    print("Contrato satisfeito. O portão está aberto para `relatar`.")
    return 0


def comando_relatar(diretorio: str, *, cfg=None) -> int:
    cfg = cfg or carregar_config()
    execucao = Path(diretorio)

    manifesto_caminho = execucao / "manifesto.json"
    if not manifesto_caminho.is_file():
        print(f"ERRO: manifesto.json não encontrado em {execucao}")
        return 2
    manifesto = json.loads(manifesto_caminho.read_text(encoding="utf-8"))

    try:
        carga = carregar_fatos(execucao / "fatos.json", estrito=True)
    except FatosInvalidos as erro:
        print(f"ERRO no portão semântico: {erro}")
        return 2

    from magalu_releases.periodos import interpretar_periodo
    from magalu_releases.vocabularios import TipoDocumento

    documentos_brutos = json.loads((execucao / "documentos.json").read_text(encoding="utf-8"))
    documentos = [
        Documento(
            documento_id=d["documento_id"],
            titulo=d["titulo"],
            tipo=TipoDocumento(d["tipo"]),
            periodo=interpretar_periodo(d["periodo"]["rotulo"]) if d.get("periodo") else None,
            url_origem=d["url_origem"],
            data_publicacao=d.get("data_publicacao"),
            arquivo_local=d.get("arquivo_local"),
            bytes=d.get("bytes"),
            sha256=d.get("sha256"),
            paginas=d.get("paginas"),
            textual=d.get("textual"),
            baixado_em=d.get("baixado_em"),
            motivo_descarte=d.get("motivo_descarte"),
        )
        for d in documentos_brutos
    ]

    periodos = tuple(manifesto["periodos"])
    resultado_series = construir_series(carga.fatos, periodos)
    variacoes = [v for s in resultado_series.series for v in calcular_variacoes(s)]

    pendencias = consolidar_pendencias(
        manifesto.get("pendencias_reconstituidas", []), resultado_series.pendencias
    )

    rotulos = {
        d.periodo.canonico: d.periodo.rotulo for d in documentos if d.periodo
    }
    rotulos = {c: rotulos.get(c, c) for c in periodos}

    caminho_resumo = execucao / "resumo.md"
    if caminho_resumo.is_file():
        resumo_texto = caminho_resumo.read_text(encoding="utf-8")
    else:
        resumo_texto = montar_esqueleto(
            n_pedido=manifesto["n_pedido"], periodos=periodos, rotulos=rotulos,
            series=resultado_series.series, variacoes=variacoes,
            pendencias=pendencias, documentos=documentos,
        )
        caminho_resumo.write_text(resumo_texto, encoding="utf-8")
        print(f"Resumo factual gerado em {caminho_resumo} (revise antes de distribuir).")

    problemas_resumo = validar_resumo(resumo_texto)
    for problema in problemas_resumo:
        print(f"AVISO no resumo: {problema}")

    relatorio = auditar(
        n_pedido=manifesto["n_pedido"], documentos=documentos, fatos=carga.fatos,
        series=resultado_series.series, variacoes=variacoes, pendencias=pendencias,
        resumo_texto=resumo_texto, periodos=periodos,
    )

    destino = execucao / f"analise_{manifesto['run_id']}.xlsx"
    gerar_excel(
        caminho=destino, n_pedido=manifesto["n_pedido"], periodos=periodos,
        documentos=documentos, fatos=carga.fatos, series=resultado_series.series,
        variacoes=variacoes, pendencias=pendencias, resumo_texto=resumo_texto,
        auditoria=relatorio.verificacoes, fonte=cfg.fonte.nome, run_id=manifesto["run_id"],
    )

    problemas_planilha = validar_planilha(
        destino, n_periodos=len(periodos), periodos=periodos
    )

    (execucao / "auditoria.json").write_text(
        json.dumps([asdict(v) for v in relatorio.verificacoes],
                   default=_serializar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    contagem = relatorio.resumo_por_resultado()
    print(f"\nPlanilha: {destino}")
    print(f"Séries: {len(resultado_series.series)} | Variações: {len(variacoes)} | "
          f"Pendências: {len(pendencias)}")
    print(f"Auditoria: {contagem['PASS']} PASS, {contagem['FAIL']} FAIL, "
          f"{contagem['ALERTA']} ALERTA")

    for verificacao in relatorio.verificacoes:
        if verificacao.resultado is not ResultadoCheck.PASS:
            print(f"  [{verificacao.resultado.value}] {verificacao.check_id}: "
                  f"esperado {verificacao.esperado}, obtido {verificacao.obtido}")

    for problema in problemas_planilha:
        print(f"  [PLANILHA] {problema}")

    if not relatorio.aprovado or problemas_planilha:
        print("\nA execução NÃO pode ser apresentada como concluída: há falhas de severidade alta.")
        return 1

    print("\nAuditoria aprovada.")
    return 0


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    if args.comando == "coletar":
        return comando_coletar(args.n)
    if args.comando == "validar-fatos":
        return comando_validar_fatos(args.run)
    if args.comando == "relatar":
        return comando_relatar(args.run)
    return 2


if __name__ == "__main__":
    sys.exit(main())
