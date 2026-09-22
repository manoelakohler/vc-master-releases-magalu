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
from dataclasses import replace as replace_documento
from pathlib import Path

from magalu_releases.analise.series import construir_series
from magalu_releases.analise.variacoes import calcular_variacoes
from magalu_releases.auditoria.checks import RelatorioAuditoria, auditar
from magalu_releases.config import carregar_config
from magalu_releases.extracao.dossie import montar_dossie, nome_execucao
from magalu_releases.extracao.texto import PdfIlegivel, extrair_paginas
from magalu_releases.fatos.esquema import FatosInvalidos, carregar_fatos
from magalu_releases.fonte.classificacao import confirmar_release
from magalu_releases.fonte.descoberta import (
    CentralNaoEncontrada,
    descobrir_documentos,
    encontrar_url_central,
    tem_paginacao,
)
from magalu_releases.fonte.download import baixar_documento, validar_pdf_textual
from magalu_releases.fonte.http import ClienteHttp, FalhaHttp
from magalu_releases.fonte.selecao import selecionar_releases
from magalu_releases.models import Documento, Pendencia
from magalu_releases.saida.dashboard import gerar_dashboard, validar_dashboard
from magalu_releases.saida.excel import gerar_excel, validar_planilha
from magalu_releases.saida.pendencias import (
    PendenciaInvalida,
    consolidar_pendencias,
    pendencia_de_dict,
)
from magalu_releases.saida.resumo import montar_esqueleto, validar_resumo
from magalu_releases.vocabularios import Gatilho, ResultadoCheck, Severidade


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

    print(f"Fonte: {cfg.fonte.base_url}")
    # A Central é alcançada pela home: sua URL carrega um token de canal e, sem
    # ele, o site responde 500. Descobrir a cada execução é o que impede que uma
    # URL congelada vire fonte oficial inexistente.
    try:
        home = cliente.obter(cfg.fonte.base_url)
        url_central = encontrar_url_central(
            home.conteudo.decode("utf-8", "replace"), base_url=cfg.fonte.base_url
        )
    except FalhaHttp as erro:
        print(f"ERRO ao acessar {cfg.fonte.base_url}: {erro}")
        print("A coleta não continua com fonte não oficial nem com dado de outra origem.")
        return 2
    except CentralNaoEncontrada as erro:
        print(f"ERRO: {erro}")
        return 2

    if cfg.fonte.dominio_oficial not in url_central:
        print(f"ERRO: a Central apontada ({url_central}) está fora do domínio oficial "
              f"{cfg.fonte.dominio_oficial}")
        return 2

    print(f"Central de Resultados: {url_central}")
    try:
        pagina = cliente.obter(url_central, referer=cfg.fonte.base_url)
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

    def pendencia_de_coleta(documento, descricao, acao):
        """Um período perdido na coleta é pendência, não aviso de terminal.

        Sem isto a execução segue com um release a menos e nada na entrega diz
        por quê — o terminal já rolou para longe quando alguém abre a planilha.
        """
        return Pendencia(
            pendencia_id=f"pen-c{len(pendencias) + 1:04d}",
            tipo=Gatilho.AMBIGUIDADE,
            severidade=Severidade.ALTA,
            descricao=descricao,
            referencias=(documento.documento_id,),
            acao_sugerida=acao,
        )

    for documento in selecao.selecionados:
        rotulo = documento.periodo.rotulo
        print(f"  baixando {documento.documento_id} ({rotulo})...")
        try:
            baixado = baixar_documento(cliente, documento, execucao / "pdfs")
        except Exception as erro:
            print(f"    FALHA: {erro}")
            pendencias.append(
                pendencia_de_coleta(
                    documento,
                    f"Release de {rotulo} não pôde ser baixado da fonte oficial: {erro}",
                    "Repetir a coleta deste período ou baixar o PDF manualmente da Central",
                )
            )
            continue

        # O servidor nomeia o arquivo no download. É a única confirmação
        # independente de que o token opaco da Central aponta mesmo para o
        # release daquele período — e não custa requisição nenhuma.
        confirmado, divergencia = confirmar_release(baixado.nome_servidor, rotulo)
        if not confirmado:
            print(f"    NÃO CONFIRMADO: {divergencia}")
            baixados.append(replace_documento(baixado, motivo_descarte=divergencia))
            pendencias.append(
                pendencia_de_coleta(
                    documento,
                    f"Release de {rotulo}: {divergencia}. O arquivo não foi analisado",
                    "Conferir na Central qual arquivo é o release deste período",
                )
            )
            continue

        if baixado.nome_servidor:
            baixado = replace_documento(baixado, titulo=baixado.nome_servidor)

        try:
            paginas = extrair_paginas(
                execucao / "pdfs" / baixado.arquivo_local, documento_id=baixado.documento_id
            )
        except PdfIlegivel as erro:
            print(f"    PDF ilegível: {erro}")
            pendencias.append(
                pendencia_de_coleta(
                    documento,
                    f"Release de {rotulo} foi baixado mas não pôde ser lido como PDF: {erro}",
                    "Conferir o arquivo baixado e repetir a coleta deste período",
                )
            )
            continue

        textual = validar_pdf_textual(
            [p.texto for p in paginas],
            minimo_caracteres=cfg.pdf.minimo_caracteres_por_pagina,
            proporcao_minima=cfg.pdf.minimo_paginas_textuais_proporcao,
        )
        baixado = replace_documento(baixado, paginas=len(paginas), textual=textual.textual)
        if not textual.textual:
            print(f"    NÃO TEXTUAL: {textual.motivo} — sem OCR, vira pendência")
            baixados.append(replace_documento(baixado, motivo_descarte=textual.motivo))
            pendencias.append(
                pendencia_de_coleta(
                    documento,
                    f"Release de {rotulo} não é textual: {textual.motivo}",
                    "Obter uma versão textual do release ou extrair os valores manualmente",
                )
            )
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
                "fonte": url_central,
                "pendencias": [asdict(p) for p in consolidar_pendencias(pendencias)],
                # Descartado sem registro é documento que sumiu: a auditoria da
                # Fase C cobra o motivo de cada um.
                "descartados": [asdict(d) for d in selecao.descartados],
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


def _documento_de_dict(bruto: dict) -> Documento:
    """Reconstrói um documento gravado pela Fase A, analisado ou descartado."""
    from magalu_releases.periodos import interpretar_periodo
    from magalu_releases.vocabularios import TipoDocumento

    return Documento(
        documento_id=bruto["documento_id"],
        titulo=bruto["titulo"],
        tipo=TipoDocumento(bruto["tipo"]),
        periodo=(
            interpretar_periodo(bruto["periodo"]["rotulo"]) if bruto.get("periodo") else None
        ),
        url_origem=bruto["url_origem"],
        data_publicacao=bruto.get("data_publicacao"),
        arquivo_local=bruto.get("arquivo_local"),
        bytes=bruto.get("bytes"),
        sha256=bruto.get("sha256"),
        paginas=bruto.get("paginas"),
        textual=bruto.get("textual"),
        baixado_em=bruto.get("baixado_em"),
        motivo_descarte=bruto.get("motivo_descarte"),
    )


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

    documentos_brutos = json.loads((execucao / "documentos.json").read_text(encoding="utf-8"))
    documentos = [_documento_de_dict(d) for d in documentos_brutos]
    descartados = [_documento_de_dict(d) for d in manifesto.get("descartados", [])]

    periodos = tuple(manifesto["periodos"])
    repetidos = sorted({c for c in periodos if periodos.count(c) > 1})
    if repetidos:
        # O manifesto é escrito por máquina: repetição aqui é coleta antiga ou
        # corrompida. Deduplicar em silêncio consertaria a régua por baixo de
        # uma análise que já foi escrita contra o dossiê torto.
        print(f"ERRO: manifesto.json repete período(s) {', '.join(repetidos)} em {execucao}")
        print("A régua da comparação precisa ter um período por posição. Refaça a coleta.")
        return 2

    resultado_series = construir_series(carga.fatos, periodos)
    variacoes = [v for s in resultado_series.series for v in calcular_variacoes(s)]

    # As pendências da coleta vêm do manifesto. A chave é exigida, não assumida
    # vazia: um default silencioso aqui apagaria da entrega tudo que a Fase A
    # encontrou — documento não classificado, período duplicado, lacuna.
    if "pendencias" not in manifesto:
        print(f"ERRO: manifesto.json sem a chave 'pendencias' em {execucao}")
        print("A execução não pode ser relatada sem as pendências da coleta.")
        return 2

    try:
        pendencias_da_coleta = [
            pendencia_de_dict(bruto) for bruto in manifesto["pendencias"]
        ]
    except PendenciaInvalida as erro:
        print(f"ERRO ao reler as pendências da coleta: {erro}")
        return 2

    pendencias = consolidar_pendencias(
        pendencias_da_coleta, resultado_series.pendencias
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
        resumo_texto=resumo_texto, periodos=periodos, descartados=descartados,
    )

    destino = execucao / f"analise_{manifesto['run_id']}.xlsx"

    def escrever(verificacoes):
        gerar_excel(
            caminho=destino, n_pedido=manifesto["n_pedido"], periodos=periodos,
            documentos=documentos, fatos=carga.fatos, series=resultado_series.series,
            variacoes=variacoes, pendencias=pendencias, resumo_texto=resumo_texto,
            auditoria=verificacoes, fonte=cfg.fonte.nome, run_id=manifesto["run_id"],
        )

    dashboard = execucao / f"dashboard_{manifesto['run_id']}.html"

    def renderizar():
        """O dashboard lê a planilha gravada — nunca os objetos em memória."""
        gerar_dashboard(
            caminho_xlsx=destino, destino=dashboard,
            run_id=manifesto["run_id"], fonte=cfg.fonte.nome,
        )

    # Duas passadas, porque a validação dos artefatos é ela própria auditoria e
    # precisa aparecer na aba: a primeira grava planilha e página, a releitura
    # das duas vira verificação, a segunda grava tudo já com essas linhas dentro.
    escrever(relatorio.verificacoes)
    renderizar()
    verificacoes_planilha = validar_planilha(
        destino, n_periodos=len(periodos), periodos=periodos
    )
    verificacoes_dashboard = validar_dashboard(
        dashboard,
        n_periodos=len(periodos),
        series_ids=[s.serie_id for s in resultado_series.series],
        rotulos=tuple(rotulos.values()),
    )
    relatorio = RelatorioAuditoria(
        relatorio.verificacoes + verificacoes_planilha + verificacoes_dashboard
    )
    escrever(relatorio.verificacoes)
    renderizar()

    # Conferência final sobre o arquivo entregue. Não realimenta o relatório —
    # senão cada passada acrescentaria linhas e nunca se chegaria ao fim.
    confirmacao = validar_planilha(destino, n_periodos=len(periodos), periodos=periodos)
    confirmacao += validar_dashboard(
        dashboard,
        n_periodos=len(periodos),
        series_ids=[s.serie_id for s in resultado_series.series],
        rotulos=tuple(rotulos.values()),
    )
    falhas_confirmacao = [
        c for c in confirmacao if c.resultado is not ResultadoCheck.PASS
    ]

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

    for falha in falhas_confirmacao:
        print(f"  [PLANILHA] {falha.check_id}: {falha.obtido} — {falha.detalhe}")

    if not relatorio.aprovado or falhas_confirmacao:
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
