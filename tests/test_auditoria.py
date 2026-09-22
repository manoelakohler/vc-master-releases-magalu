"""Auditoria automática: sem ela não há conclusão.

O relatório registra também o que passou. Uma auditoria que só aparece quando
falha não prova que rodou.
"""

import pytest

from magalu_releases.auditoria.checks import (
    auditar,
    varrer_linguagem_promocional,
    varrer_linguagem_recomendacao,
)
from magalu_releases.models import PontoSerie, Serie, Variacao
from magalu_releases.periodos import interpretar_periodo
from magalu_releases.vocabularios import (
    Base,
    BaseComparacao,
    Confianca,
    Periodicidade,
    ResultadoCheck,
    Segmento,
    TipoDocumento,
    TipoValor,
)

PERIODOS = ("2025-Q4", "2026-Q1", "2026-Q2")
ROTULOS = {"2025-Q4": "4T25", "2026-Q1": "1T26", "2026-Q2": "2T26"}


@pytest.fixture
def cenario(fato_valido, documento_valido):
    def montar(**ajustes):
        fatos = [
            fato_valido(
                fato_id=f"f-{c}",
                periodo=interpretar_periodo(ROTULOS[c]),
                documento_id=f"doc-{c}",
                valor_original="100,0",
                valor_normalizado=100.0,
                trecho_fonte="Receita Líquida 100,0",
            )
            for c in PERIODOS
        ]
        documentos = [
            documento_valido(
                documento_id=f"doc-{c}",
                periodo=interpretar_periodo(ROTULOS[c]),
                titulo=f"Release {ROTULOS[c]}",
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
            pontos=tuple(
                PontoSerie(c, f"f-{c}", 100.0, "100,0") for c in PERIODOS
            ),
            confianca_minima=Confianca.ALTA,
        )
        base = dict(
            n_pedido=3,
            documentos=documentos,
            fatos=fatos,
            series=[serie],
            variacoes=[],
            pendencias=[],
            resumo_texto="A receita líquida somou 100,0 em 2T26.",
            periodos=PERIODOS,
        )
        base.update(ajustes)
        return base

    return montar


class TestRelatorio:
    def test_registra_tambem_o_que_passou(self, cenario):
        r = auditar(**cenario())
        assert any(v.resultado is ResultadoCheck.PASS for v in r.verificacoes)

    def test_cenario_integro_e_aprovado(self, cenario):
        r = auditar(**cenario())
        assert r.aprovado is True
        assert r.falhas_altas == ()

    def test_todo_check_tem_identificador_e_descricao(self, cenario):
        r = auditar(**cenario())
        assert all(v.check_id and v.descricao for v in r.verificacoes)

    def test_cobre_as_familias_de_verificacao(self, cenario):
        ids = {v.check_id.split("_")[0] for v in auditar(**cenario()).verificacoes}
        assert {"sel", "evi", "val", "cmp", "pen", "lng"} <= ids


class TestSelecao:
    def test_quantidade_menor_que_n_e_sinalizada(self, cenario):
        r = auditar(**cenario(n_pedido=5))
        check = [v for v in r.verificacoes if v.check_id == "sel_quantidade"][0]
        assert check.resultado is not ResultadoCheck.PASS

    def test_periodo_duplicado_reprova(self, cenario, documento_valido):
        dados = cenario()
        dados["documentos"] = list(dados["documentos"]) + [
            documento_valido(documento_id="doc-extra", periodo=interpretar_periodo("2T26"))
        ]
        r = auditar(**dados)
        assert [v for v in r.verificacoes if v.check_id == "sel_periodos_unicos"][0].resultado is (
            ResultadoCheck.FAIL
        )

    def test_documento_que_nao_e_release_reprova(self, cenario, documento_valido):
        dados = cenario()
        dados["documentos"] = list(dados["documentos"]) + [
            documento_valido(
                documento_id="doc-itr",
                tipo=TipoDocumento.ITR_DFP,
                periodo=interpretar_periodo("3T25"),
            )
        ]
        r = auditar(**dados)
        assert [v for v in r.verificacoes if v.check_id == "sel_tipo"][0].resultado is (
            ResultadoCheck.FAIL
        )


class TestEvidencia:
    def test_fato_sem_documento_correspondente_reprova(self, cenario, fato_valido):
        dados = cenario()
        dados["fatos"] = list(dados["fatos"]) + [
            fato_valido(fato_id="f-orfao", documento_id="doc-inexistente")
        ]
        r = auditar(**dados)
        assert [v for v in r.verificacoes if v.check_id == "evi_documento_existe"][0].resultado is (
            ResultadoCheck.FAIL
        )

    def test_ponto_de_serie_sem_fato_conhecido_reprova(self, cenario):
        dados = cenario()
        serie = dados["series"][0]
        from dataclasses import replace

        dados["series"] = [
            replace(
                serie,
                pontos=(PontoSerie("2025-Q4", "f-fantasma", 1.0, "1,0"),) + serie.pontos[1:],
            )
        ]
        r = auditar(**dados)
        assert [
            v for v in r.verificacoes if v.check_id == "evi_rastro_comparativo"
        ][0].resultado is ResultadoCheck.FAIL


class TestValores:
    def test_unidade_incoerente_na_serie_reprova(self, cenario):
        from dataclasses import replace

        dados = cenario()
        dados["series"] = [replace(dados["series"][0], unidade_serie=None)]
        r = auditar(**dados)
        assert any(
            v.check_id == "val_unidade_serie" and v.resultado is not ResultadoCheck.PASS
            for v in r.verificacoes
        )


class TestComparacao:
    def test_serie_com_numero_errado_de_posicoes_reprova(self, cenario):
        from dataclasses import replace

        dados = cenario()
        dados["series"] = [replace(dados["series"][0], pontos=dados["series"][0].pontos[:2])]
        r = auditar(**dados)
        assert [v for v in r.verificacoes if v.check_id == "cmp_n_posicoes"][0].resultado is (
            ResultadoCheck.FAIL
        )

    def test_variacao_sem_base_declarada_reprova(self, cenario):
        dados = cenario()
        dados["variacoes"] = [
            Variacao(
                serie_id="s-1",
                periodo_de="2025-Q4",
                periodo_para="2026-Q1",
                base_comparacao=None,
                calculada=True,
                variacao_abs=1.0,
            )
        ]
        r = auditar(**dados)
        assert [v for v in r.verificacoes if v.check_id == "cmp_base_declarada"][0].resultado is (
            ResultadoCheck.FAIL
        )

    def test_percentual_com_variacao_percentual_reprova(self, cenario):
        dados = cenario()
        dados["variacoes"] = [
            Variacao(
                serie_id="receita_liquida-consolidado-reportado-trimestre-absoluto",
                periodo_de="2025-Q4",
                periodo_para="2026-Q1",
                base_comparacao=BaseComparacao.PERIODO_ANTERIOR,
                variacao_pct=10.0,
                variacao_pp=2.0,
                calculada=True,
            )
        ]
        r = auditar(**dados)
        assert [v for v in r.verificacoes if v.check_id == "val_pp_vs_pct"][0].resultado is (
            ResultadoCheck.FAIL
        )


class TestLinguagemRecomendacao:
    @pytest.mark.parametrize(
        "texto",
        [
            "Recomendamos a compra das ações.",
            "O investidor deve vender a ação.",
            "Sugerimos manter a posição em MGLU3.",
            "recomenda-se cautela na compra do papel",
            "vale a pena comprar ações da companhia",
        ],
    )
    def test_detecta_recomendacao(self, texto):
        assert varrer_linguagem_recomendacao(texto)

    @pytest.mark.parametrize(
        "texto",
        [
            "As vendas totais somaram R$ 9.856,4 milhões no 2T25.",
            "A receita de venda de mercadorias cresceu 8,2%.",
            "O volume de vendas em lojas físicas caiu 3,1%.",
            "A companhia manteve o número de lojas em 1.245.",
            "",
        ],
    )
    def test_nao_confunde_metrica_de_vendas_com_recomendacao(self, texto):
        assert varrer_linguagem_recomendacao(texto) == ()

    def test_check_reprova_resumo_com_recomendacao(self, cenario):
        r = auditar(**cenario(resumo_texto="Recomendamos a compra das ações da companhia."))
        assert [
            v for v in r.verificacoes if v.check_id == "lng_sem_recomendacao"
        ][0].resultado is ResultadoCheck.FAIL
        assert r.aprovado is False


class TestLinguagemPromocional:
    @pytest.mark.parametrize(
        "texto",
        [
            "Resultado sólido no trimestre.",
            "Desempenho robusto do e-commerce.",
            "Recuperação consistente das margens.",
            "Crescimento expressivo da receita.",
            "A companhia atravessa um momento favorável.",
        ],
    )
    def test_detecta_adjetivacao_avaliativa(self, texto):
        assert varrer_linguagem_promocional(texto)

    @pytest.mark.parametrize(
        "texto",
        [
            "A receita líquida passou de 9.112,0 para 9.856,4, variação de 8,2%.",
            "A margem bruta variou 0,2 p.p. entre 2T24 e 2T25.",
            "O EBITDA ajustado não foi reportado neste release.",
        ],
    )
    def test_texto_factual_passa(self, texto):
        assert varrer_linguagem_promocional(texto) == ()

    def test_check_alerta_sobre_promocional(self, cenario):
        r = auditar(**cenario(resumo_texto="Resultado sólido e desempenho robusto."))
        assert [
            v for v in r.verificacoes if v.check_id == "lng_sem_promocional"
        ][0].resultado is not ResultadoCheck.PASS
