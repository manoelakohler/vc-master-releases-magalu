"""Geração e validação da planilha.

A planilha é registro auditável, não modelo recalculável: nenhum valor vindo dos
documentos é fórmula viva, porque uma fórmula que recalcula pode divergir do que
foi extraído e auditado.

O teste central é a reabertura: gravar sem erro não prova que o conteúdo está
correto.
"""

import pytest
from openpyxl import load_workbook

from magalu_releases.auditoria.checks import auditar
from magalu_releases.models import PontoSerie, Serie, Variacao
from magalu_releases.periodos import interpretar_periodo
from magalu_releases.saida.excel import ABAS, gerar_excel, validar_planilha
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
def pacote(fato_valido, documento_valido):
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
    relatorio = auditar(
        n_pedido=3,
        documentos=documentos,
        fatos=fatos,
        series=[serie],
        variacoes=variacoes,
        pendencias=[],
        resumo_texto="A receita líquida somou 9.856,4 em 4T25.",
        periodos=PERIODOS,
    )
    return dict(
        caminho=None,
        n_pedido=3,
        periodos=PERIODOS,
        documentos=documentos,
        fatos=fatos,
        series=[serie],
        variacoes=variacoes,
        pendencias=[],
        resumo_texto="A receita líquida somou 9.856,4 em 4T25.",
        auditoria=relatorio.verificacoes,
        fonte="Magazine Luiza — Central de Resultados",
        run_id="run-teste",
    )


@pytest.fixture
def planilha(tmp_path, pacote):
    destino = tmp_path / "analise.xlsx"
    pacote["caminho"] = destino
    gerar_excel(**pacote)
    return destino


class TestEstrutura:
    def test_as_seis_abas_na_ordem(self, planilha):
        wb = load_workbook(planilha)
        assert wb.sheetnames == list(ABAS)

    def test_nomes_exatos(self):
        assert ABAS == (
            "Resumo",
            "Comparativo",
            "Evidências",
            "Documentos",
            "Pendências",
            "Auditoria",
        )

    def test_arquivo_reabre(self, planilha):
        assert load_workbook(planilha) is not None


class TestComparativo:
    def test_tem_n_colunas_de_periodo(self, planilha):
        wb = load_workbook(planilha)
        cabecalhos = [c.value for c in wb["Comparativo"][1]]
        assert sum(1 for h in cabecalhos if h in ROTULOS.values()) == 3

    def test_periodos_em_ordem_crescente(self, planilha):
        wb = load_workbook(planilha)
        cabecalhos = [c.value for c in wb["Comparativo"][1]]
        posicoes = [cabecalhos.index(ROTULOS[c]) for c in PERIODOS]
        assert posicoes == sorted(posicoes)

    def test_posicao_ausente_fica_vazia_e_nao_zero(self, planilha):
        wb = load_workbook(planilha)
        aba = wb["Comparativo"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("1T26") + 1
        valor = aba.cell(row=2, column=coluna).value
        assert valor is None or valor == ""
        assert valor != 0

    def test_valor_presente_aparece(self, planilha):
        wb = load_workbook(planilha)
        aba = wb["Comparativo"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("4T25") + 1
        assert aba.cell(row=2, column=coluna).value == pytest.approx(9856.4)

    def test_unidade_tem_coluna_propria(self, planilha):
        wb = load_workbook(planilha)
        cabecalhos = [c.value for c in wb["Comparativo"][1]]
        assert any("nidade" in str(h) for h in cabecalhos)


class TestEvidencias:
    def test_uma_linha_por_fato(self, planilha):
        wb = load_workbook(planilha)
        assert wb["Evidências"].max_row == 1 + 3

    def test_valor_original_continua_texto(self, planilha):
        """Deixar o Excel reinterpretar 9.856,4 destrói a coluna que prova o documento."""
        wb = load_workbook(planilha)
        aba = wb["Evidências"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("valor_original") + 1
        celula = aba.cell(row=2, column=coluna)
        assert celula.value == "9.856,4"
        assert isinstance(celula.value, str)
        assert celula.number_format == "@"

    def test_trecho_fonte_preservado(self, planilha):
        wb = load_workbook(planilha)
        aba = wb["Evidências"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("trecho_fonte") + 1
        assert "9.856,4" in aba.cell(row=2, column=coluna).value

    def test_pagina_e_documento_presentes(self, planilha):
        wb = load_workbook(planilha)
        cabecalhos = [c.value for c in wb["Evidências"][1]]
        assert "pagina" in cabecalhos
        assert "documento_id" in cabecalhos


class TestDocumentosEResumo:
    def test_documentos_trazem_hash_e_url(self, planilha):
        wb = load_workbook(planilha)
        cabecalhos = [c.value for c in wb["Documentos"][1]]
        assert "sha256" in cabecalhos
        assert "url_origem" in cabecalhos

    def test_resumo_mostra_n_pedido_e_obtido(self, planilha):
        wb = load_workbook(planilha)
        texto = "\n".join(
            str(c.value) for linha in wb["Resumo"].iter_rows() for c in linha if c.value
        )
        assert "N pedido" in texto
        assert "N obtido" in texto

    def test_resumo_contem_o_texto_executivo(self, planilha):
        wb = load_workbook(planilha)
        texto = "\n".join(
            str(c.value) for linha in wb["Resumo"].iter_rows() for c in linha if c.value
        )
        assert "receita líquida" in texto.lower()


class TestPendenciasEAuditoria:
    def test_pendencias_vazias_declaram_isso(self, planilha):
        """Aba vazia é ambígua: não se sabe se nada foi achado ou se não rodou."""
        wb = load_workbook(planilha)
        aba = wb["Pendências"]
        assert aba.max_row >= 2
        texto = " ".join(str(c.value or "") for c in aba[2])
        assert "nenhuma" in texto.lower()

    def test_auditoria_registra_o_que_passou(self, planilha):
        wb = load_workbook(planilha)
        aba = wb["Auditoria"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("resultado") + 1
        resultados = {aba.cell(row=r, column=coluna).value for r in range(2, aba.max_row + 1)}
        assert "PASS" in resultados


class TestSemFormulas:
    def test_nenhuma_celula_e_formula(self, planilha):
        """Registro auditável: fórmula viva pode divergir do que foi auditado."""
        wb = load_workbook(planilha)
        for aba in wb.worksheets:
            for linha in aba.iter_rows():
                for celula in linha:
                    if isinstance(celula.value, str):
                        assert not celula.value.startswith("=")


class TestValidacaoComoVerificacao:
    """A validação da planilha é auditoria, e auditoria vira linha na aba.

    Enquanto o resultado saía como texto no terminal, a aba Auditoria alegava
    uma cobertura que não tinha: os checks `xls_*` da skill não apareciam em
    lugar nenhum do arquivo entregue.
    """

    IDS = ("xls_abas", "xls_colunas_periodo", "xls_texto_preservado", "xls_reabertura")

    def test_devolve_verificacoes_com_os_ids_da_skill(self, planilha):
        verificacoes = validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)
        assert tuple(v.check_id for v in verificacoes) == self.IDS

    def test_planilha_bem_formada_passa_em_todas(self, planilha):
        verificacoes = validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)
        assert all(v.resultado is ResultadoCheck.PASS for v in verificacoes)

    def test_aba_faltando_reprova_xls_abas(self, planilha):
        wb = load_workbook(planilha)
        del wb["Pendências"]
        wb.save(planilha)
        por_id = {v.check_id: v for v in validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)}
        assert por_id["xls_abas"].resultado is ResultadoCheck.FAIL

    def test_coluna_de_periodo_faltando_reprova_o_check_certo(self, planilha):
        por_id = {
            v.check_id: v
            for v in validar_planilha(
                planilha, n_periodos=4, periodos=PERIODOS + ("2026-Q3",)
            )
        }
        assert por_id["xls_colunas_periodo"].resultado is ResultadoCheck.FAIL
        assert por_id["xls_abas"].resultado is ResultadoCheck.PASS

    def test_texto_preservado_cobre_trecho_fonte(self, planilha):
        """O trecho é a evidência: reinterpretado pelo Excel, deixa de provar."""
        wb = load_workbook(planilha)
        aba = wb["Evidências"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("trecho_fonte") + 1
        aba.cell(row=2, column=coluna).number_format = "General"
        wb.save(planilha)

        por_id = {v.check_id: v for v in validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)}
        assert por_id["xls_texto_preservado"].resultado is ResultadoCheck.FAIL

    def test_texto_preservado_olha_todas_as_linhas(self, planilha):
        wb = load_workbook(planilha)
        aba = wb["Evidências"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("valor_original") + 1
        aba.cell(row=aba.max_row, column=coluna).number_format = "General"
        wb.save(planilha)

        por_id = {v.check_id: v for v in validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)}
        assert por_id["xls_texto_preservado"].resultado is ResultadoCheck.FAIL


class TestOrdemDasColunasDePeriodo:
    """O cabeçalho pode vir no rótulo do documento (2T26) ou no canônico (2026-Q2).

    Quando nenhum documento trouxe rótulo, a planilha cai no canônico. Se o
    check só entende rótulo, ele passa sem olhar nada — e uma coluna fora de
    ordem cronológica atravessa a auditoria alegando ter sido verificada.
    """

    def _trocar_cabecalhos(self, planilha, novos):
        wb = load_workbook(planilha)
        aba = wb["Comparativo"]
        cabecalhos = [c.value for c in aba[1]]
        colunas = [i + 1 for i, h in enumerate(cabecalhos) if h in ROTULOS.values()]
        for coluna, valor in zip(colunas, novos):
            aba.cell(row=1, column=coluna).value = valor
        wb.save(planilha)

    def test_canonicos_em_ordem_passam(self, planilha):
        self._trocar_cabecalhos(planilha, ["2025-Q4", "2026-Q1", "2026-Q2"])
        por_id = {v.check_id: v for v in validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)}
        assert por_id["xls_colunas_periodo"].resultado is ResultadoCheck.PASS

    def test_canonicos_fora_de_ordem_reprovam(self, planilha):
        self._trocar_cabecalhos(planilha, ["2026-Q2", "2025-Q4", "2026-Q1"])
        por_id = {v.check_id: v for v in validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)}
        assert por_id["xls_colunas_periodo"].resultado is ResultadoCheck.FAIL

    def test_rotulos_fora_de_ordem_reprovam(self, planilha):
        self._trocar_cabecalhos(planilha, ["2T26", "4T25", "1T26"])
        por_id = {v.check_id: v for v in validar_planilha(planilha, n_periodos=3, periodos=PERIODOS)}
        assert por_id["xls_colunas_periodo"].resultado is ResultadoCheck.FAIL


class TestNomeDoServidorNaPlanilha:
    """A confirmação do servidor é evidência e pertence à entrega.

    O link da Central não diz nada sobre o arquivo. Quem receber a planilha
    precisa poder ver que o PDF baixado se identificou como o release daquele
    período — e o nome que o servidor devolveu é essa prova.
    """

    def test_coluna_existe(self, planilha):
        aba = load_workbook(planilha)["Documentos"]
        assert "nome_servidor" in [c.value for c in aba[1]]

    def test_nome_e_gravado_como_texto(self, planilha):
        aba = load_workbook(planilha)["Documentos"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("nome_servidor") + 1
        celula = aba.cell(row=2, column=coluna)
        assert celula.value == "MGLU_ER_2T26_POR.pdf"
        assert celula.number_format == "@"
