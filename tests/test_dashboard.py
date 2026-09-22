"""Dashboard HTML: a mesma entrega, em forma de página.

O dashboard é gerado **a partir da planilha já gravada**, não dos objetos em
memória. Isso não é detalhe de implementação: garante que a página mostra
exatamente o que está no arquivo entregue, e permite re-renderizar execuções
antigas a partir do artefato.

A regra que atravessa a planilha atravessa a página: de qualquer número exibido
é possível chegar à evidência — documento, página e trecho literal.
"""

import re

import pytest
from openpyxl import load_workbook

from magalu_releases.auditoria.checks import (
    varrer_linguagem_promocional,
    varrer_linguagem_recomendacao,
)
from magalu_releases.auditoria.checks import auditar
from magalu_releases.models import PontoSerie, Serie, Variacao
from magalu_releases.periodos import interpretar_periodo
from magalu_releases.saida.dashboard import gerar_dashboard, validar_dashboard
from magalu_releases.saida.excel import gerar_excel
from magalu_releases.vocabularios import (
    Base,
    BaseComparacao,
    Confianca,
    Periodicidade,
    ResultadoCheck,
    Segmento,
    TipoValor,
)

PERIODOS = ("2025-Q4", "2026-Q1", "2026-Q2")
ROTULOS = {"2025-Q4": "4T25", "2026-Q1": "1T26", "2026-Q2": "2T26"}


@pytest.fixture
def planilha(tmp_path, fato_valido, documento_valido):
    """Uma planilha real: o dashboard só sabe ler o artefato gravado."""
    fatos = [
        fato_valido(
            fato_id=f"f-{c}",
            periodo=interpretar_periodo(ROTULOS[c]),
            documento_id=f"doc-{c}",
            valor_original="9.856,4",
            valor_normalizado=9856.4,
            trecho_fonte="Receita Líquida 9.856,4 9.112,0",
        )
        for c in PERIODOS
    ]
    documentos = [
        documento_valido(
            documento_id=f"doc-{c}",
            nome_servidor="MGLU_ER_2T26_POR.pdf",
            periodo=interpretar_periodo(ROTULOS[c]),
            titulo=f"Release de Resultados {ROTULOS[c]}",
        )
        for c in PERIODOS
    ]
    serie = Serie(
        serie_id="receita_liquida-consolidado-reportado-trimestre-absoluto",
        metrica_id="receita_liquida",
        metrica_rotulo="Receita Líquida",
        segmento=Segmento.CONSOLIDADO,
        base=Base.REPORTADO,
        periodicidade=Periodicidade.TRIMESTRE,
        tipo_valor=TipoValor.ABSOLUTO,
        unidade_serie="R$ milhões",
        pontos=(
            PontoSerie("2025-Q4", "f-2025-Q4", 9856.4, "9.856,4"),
            PontoSerie("2026-Q1", None, None, None),
            PontoSerie("2026-Q2", "f-2026-Q2", 10112.0, "10.112,0"),
        ),
        confianca_minima=Confianca.ALTA,
    )
    variacoes = [
        Variacao(
            serie_id=serie.serie_id,
            periodo_de="2025-Q4",
            periodo_para="2026-Q1",
            base_comparacao=BaseComparacao.PERIODO_ANTERIOR,
            calculada=False,
            motivo_nao_calculada="valor ausente em 2026-Q1",
        )
    ]
    resumo = "A receita líquida somou 9.856,4 em 4T25."
    relatorio = auditar(
        n_pedido=3, documentos=documentos, fatos=fatos, series=[serie],
        variacoes=variacoes, pendencias=[], resumo_texto=resumo, periodos=PERIODOS,
    )
    destino = tmp_path / "analise.xlsx"
    gerar_excel(
        caminho=destino, n_pedido=3, periodos=PERIODOS, documentos=documentos,
        fatos=fatos, series=[serie], variacoes=variacoes, pendencias=[],
        resumo_texto=resumo, auditoria=relatorio.verificacoes,
        fonte="Magazine Luiza — Central de Resultados", run_id="run-teste",
    )
    return destino


def texto_visivel(html: str) -> str:
    """Tira marcação e estilo, deixando o que a pessoa lê.

    Colapsa espaço em branco porque a quebra de linha do HTML não existe para
    quem lê a página: "releases\n públicos" é uma frase só na tela.
    """
    sem_script = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sem_script))


@pytest.fixture
def dashboard(tmp_path, planilha):
    destino = tmp_path / "dashboard.html"
    gerar_dashboard(
        caminho_xlsx=planilha,
        destino=destino,
        run_id="run-teste",
        fonte="Magazine Luiza — Central de Resultados",
    )
    return destino


@pytest.fixture
def html(dashboard):
    return dashboard.read_text(encoding="utf-8")


class TestPaginaUnica:
    def test_gera_o_arquivo(self, dashboard):
        assert dashboard.is_file()

    def test_e_uma_pagina_so(self, dashboard, tmp_path):
        """Nada de arquivos satélite: a entrega é um arquivo que se abre sozinho."""
        assert [p.name for p in tmp_path.glob("*.html")] == ["dashboard.html"]

    def test_nao_depende_de_rede(self, html):
        """Um relatório que precisa de internet para renderizar não é auditável offline."""
        assert "http://" not in html
        assert "https://cdn" not in html
        assert not re.search(r"<script[^>]+\bsrc=", html, re.I)
        assert not re.search(r'<link[^>]+rel=["\']?stylesheet', html, re.I)

    def test_declara_modo_escuro(self, html):
        assert "prefers-color-scheme: dark" in html
        assert 'data-theme="dark"' in html


class TestEscopo:
    def test_mostra_n_pedido_e_obtido(self, html):
        visivel = texto_visivel(html)
        assert "N pedido" in visivel or "Releases pedidos" in visivel
        assert "3" in visivel

    def test_lista_os_periodos_em_ordem(self, html):
        visivel = texto_visivel(html)
        posicoes = [visivel.index(r) for r in ("4T25", "1T26", "2T26")]
        assert posicoes == sorted(posicoes)

    def test_traz_os_documentos_com_hash(self, html):
        assert "a" * 64 in html, "o SHA-256 é o que torna a execução reproduzível"


class TestComparativo:
    def test_traz_todas_as_series(self, dashboard, planilha):
        aba = load_workbook(planilha)["Comparativo"]
        ids = {aba.cell(row=l, column=1).value for l in range(2, aba.max_row + 1)}
        html = dashboard.read_text(encoding="utf-8")
        assert all(sid in html for sid in ids)

    def test_valor_ausente_nao_vira_zero(self, html):
        """A posição vazia do 1T26 precisa aparecer como ausência, não como 0.

        O assert olha só as células de período: zero é valor legítimo em outros
        lugares da página ("Pendências abertas: 0"), e confundir os dois esconde
        justamente o que este teste existe para pegar.
        """
        celulas = re.findall(r'<td class="num">([^<]*)</td>', html)
        assert "—" in celulas, "a posição sem fato precisa aparecer como ausência"
        assert "0" not in celulas[:3], "posição ausente não pode virar zero"

    def test_variacao_suprimida_mostra_o_motivo(self, html):
        assert "valor ausente em 2026-Q1" in texto_visivel(html)


class TestEvidencia:
    def test_todo_fato_tem_documento_pagina_e_trecho(self, dashboard, planilha):
        aba = load_workbook(planilha)["Evidências"]
        cab = [c.value for c in aba[1]]
        html = dashboard.read_text(encoding="utf-8")
        for linha in range(2, aba.max_row + 1):
            valores = {n: aba.cell(row=linha, column=i + 1).value for i, n in enumerate(cab)}
            assert valores["documento_id"] in html
            assert valores["trecho_fonte"] in html
            assert f"{valores['pagina']}" in html

    def test_valor_original_preservado_literalmente(self, html):
        assert "9.856,4" in html


class TestPendenciasEAuditoria:
    def test_ausencia_de_pendencia_e_declarada(self, html):
        """Seção vazia é ambígua: não se sabe se nada foi achado ou se não rodou."""
        assert "Nenhuma pendência" in texto_visivel(html)

    def test_lista_os_checks_de_auditoria(self, dashboard, planilha):
        aba = load_workbook(planilha)["Auditoria"]
        ids = {aba.cell(row=l, column=1).value for l in range(2, aba.max_row + 1)}
        html = dashboard.read_text(encoding="utf-8")
        assert all(cid in html for cid in ids)

    def test_mostra_o_desfecho_da_auditoria(self, html):
        assert "PASS" in html


class TestLinguagem:
    def test_sem_recomendacao_de_investimento(self, html):
        assert varrer_linguagem_recomendacao(texto_visivel(html)) == ()

    def test_sem_adjetivacao_avaliativa(self, html):
        assert varrer_linguagem_promocional(texto_visivel(html)) == ()


class TestValidacao:
    def test_dashboard_completo_passa(self, dashboard, planilha):
        aba = load_workbook(planilha)["Comparativo"]
        ids = [aba.cell(row=l, column=1).value for l in range(2, aba.max_row + 1)]
        checks = validar_dashboard(dashboard, n_periodos=3, series_ids=ids, rotulos=("4T25",))
        assert all(c.resultado is ResultadoCheck.PASS for c in checks)
        assert [c.check_id for c in checks] == ["dsh_completo"]

    def test_serie_faltando_reprova(self, dashboard):
        checks = validar_dashboard(
            dashboard, n_periodos=3, series_ids=["serie-que-nao-esta-la"], rotulos=("4T25",)
        )
        assert checks[0].resultado is ResultadoCheck.FAIL
        assert "serie-que-nao-esta-la" in checks[0].detalhe

    def test_periodo_faltando_reprova(self, dashboard):
        checks = validar_dashboard(dashboard, n_periodos=3, series_ids=[], rotulos=("3T30",))
        assert checks[0].resultado is ResultadoCheck.FAIL

    def test_arquivo_ausente_reprova(self, tmp_path):
        checks = validar_dashboard(
            tmp_path / "nao-existe.html", n_periodos=3, series_ids=[], rotulos=()
        )
        assert checks[0].resultado is ResultadoCheck.FAIL


class TestAutoria:
    """Página pública com o nome da companhia precisa dizer quem a fez.

    Sem isso, um leitor que chega pelo link pode entender o dashboard como
    publicação da própria Magazine Luiza — o que ele não é, e o que nenhuma
    quantidade de rodapé conserta depois.
    """

    def test_declara_analise_independente(self, html):
        visivel = texto_visivel(html)
        assert "independente" in visivel.lower()

    def test_cita_a_fonte_oficial(self, html):
        assert "Central de Resultados" in texto_visivel(html)

    def test_nao_se_apresenta_como_publicacao_da_companhia(self, html):
        visivel = texto_visivel(html).lower()
        assert "releases públicos" in visivel or "releases publicos" in visivel
