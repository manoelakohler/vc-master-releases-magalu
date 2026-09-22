"""Agrupamento de fatos em séries comparáveis.

A identidade da série é a tupla completa. É ela que impede lucro ajustado de
virar reportado e trimestre de virar acumulado — misturas que produzem uma série
coerente na aparência e falsa no conteúdo.

A série tem sempre N posições. Período ausente é None na sua posição: a lista
não encolhe e os valores não deslizam para tapar o buraco, porque deslize é como
uma série inteira passa a comparar períodos errados.
"""

import pytest

from magalu_releases.analise.series import construir_series
from magalu_releases.periodos import interpretar_periodo
from magalu_releases.vocabularios import (
    Base,
    Confianca,
    Gatilho,
    Periodicidade,
    Segmento,
    TipoValor,
)

PERIODOS = ("2025-Q4", "2026-Q1", "2026-Q2")
ROTULOS = {"2025-Q4": "4T25", "2026-Q1": "1T26", "2026-Q2": "2T26"}


def fato_em(fabrica, canonico, valor, sufixo="", **extra):
    return fabrica(
        fato_id=("f-" + canonico + "-" + sufixo).rstrip("-"),
        periodo=interpretar_periodo(ROTULOS[canonico]),
        valor_original=str(valor),
        valor_normalizado=float(str(valor).replace(",", ".")),
        trecho_fonte="Linha " + str(valor),
        **extra,
    )


class TestPosicoes:
    def test_serie_tem_sempre_n_posicoes(self, fato_valido):
        fatos = [fato_em(fato_valido, "2026-Q2", "9856.4")]
        series = construir_series(fatos, PERIODOS).series
        assert len(series) == 1
        assert len(series[0].pontos) == 3

    def test_periodo_ausente_e_none_na_propria_posicao(self, fato_valido):
        fatos = [fato_em(fato_valido, "2026-Q2", "9856.4")]
        pontos = construir_series(fatos, PERIODOS).series[0].pontos
        assert [p.valor_normalizado for p in pontos] == [None, None, pytest.approx(9856.4)]

    def test_valores_nao_deslizam_para_tapar_buraco(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2025-Q4", "100.0"),
            fato_em(fato_valido, "2026-Q2", "300.0"),
        ]
        pontos = construir_series(fatos, PERIODOS).series[0].pontos
        assert pontos[0].valor_normalizado == pytest.approx(100.0)
        assert pontos[1].valor_normalizado is None
        assert pontos[2].valor_normalizado == pytest.approx(300.0)

    def test_ordem_das_posicoes_e_cronologica_crescente(self, fato_valido):
        fatos = [fato_em(fato_valido, c, "1.0") for c in reversed(PERIODOS)]
        pontos = construir_series(fatos, PERIODOS).series[0].pontos
        assert [p.periodo_canonico for p in pontos] == list(PERIODOS)

    def test_evidencia_fica_acessivel_no_ponto(self, fato_valido):
        fatos = [fato_em(fato_valido, "2026-Q2", "9856.4")]
        ponto = construir_series(fatos, PERIODOS).series[0].pontos[2]
        assert ponto.fato_id
        assert ponto.valor_original == "9856.4"


class TestSeparacaoDeSeries:
    def test_ajustado_e_reportado_nao_se_misturam(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2026-Q2", "988.7", sufixo="r", base=Base.REPORTADO),
            fato_em(fato_valido, "2026-Q2", "1012.3", sufixo="a", base=Base.AJUSTADO),
        ]
        assert len(construir_series(fatos, PERIODOS).series) == 2

    def test_trimestre_e_acumulado_nao_se_misturam(self, fato_valido):
        fatos = [
            fato_em(
                fato_valido, "2026-Q2", "1.0", sufixo="t", periodicidade=Periodicidade.TRIMESTRE
            ),
            fato_em(
                fato_valido, "2026-Q2", "2.0", sufixo="a", periodicidade=Periodicidade.ACUMULADO
            ),
        ]
        assert len(construir_series(fatos, PERIODOS).series) == 2

    def test_segmentos_nao_se_misturam(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2026-Q2", "1.0", sufixo="c", segmento=Segmento.CONSOLIDADO),
            fato_em(fato_valido, "2026-Q2", "2.0", sufixo="e", segmento=Segmento.ECOMMERCE),
        ]
        assert len(construir_series(fatos, PERIODOS).series) == 2

    def test_percentual_e_absoluto_nao_se_misturam(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2026-Q2", "1.0", sufixo="a", tipo_valor=TipoValor.ABSOLUTO),
            fato_em(fato_valido, "2026-Q2", "2.0", sufixo="p", tipo_valor=TipoValor.PERCENTUAL),
        ]
        assert len(construir_series(fatos, PERIODOS).series) == 2

    def test_mesma_chave_forma_uma_serie_so(self, fato_valido):
        fatos = [fato_em(fato_valido, c, "1.0") for c in PERIODOS]
        assert len(construir_series(fatos, PERIODOS).series) == 1


class TestEscala:
    def test_unifica_escala_dentro_da_serie(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2025-Q4", "9000000.0", sufixo="k", unidade="R$ mil"),
            fato_em(fato_valido, "2026-Q2", "9856.4", sufixo="m", unidade="R$ milhões"),
        ]
        serie = construir_series(fatos, PERIODOS).series[0]
        assert serie.unidade_serie == "R$ milhões"
        assert serie.pontos[0].valor_normalizado == pytest.approx(9000.0)

    def test_escala_inconvertivel_marca_revisao(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2025-Q4", "10.0", sufixo="l", unidade="lojas"),
            fato_em(fato_valido, "2026-Q2", "20.0", sufixo="m", unidade="R$ milhões"),
        ]
        resultado = construir_series(fatos, PERIODOS)
        assert resultado.series[0].revisao_humana is True
        assert resultado.pendencias


class TestConflito:
    def test_dois_fatos_no_mesmo_periodo_geram_conflito(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2026-Q2", "9856.4", sufixo="a"),
            fato_em(fato_valido, "2026-Q2", "9999.9", sufixo="b"),
        ]
        resultado = construir_series(fatos, PERIODOS)
        assert any(p.tipo is Gatilho.CONFLITO for p in resultado.pendencias)

    def test_conflito_preserva_os_dois_valores(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2026-Q2", "9856.4", sufixo="a"),
            fato_em(fato_valido, "2026-Q2", "9999.9", sufixo="b"),
        ]
        pendencias = construir_series(fatos, PERIODOS).pendencias
        conflito = [p for p in pendencias if p.tipo is Gatilho.CONFLITO][0]
        assert len(conflito.valores_conflitantes) == 2

    def test_valores_iguais_no_mesmo_periodo_nao_sao_conflito(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2026-Q2", "9856.4", sufixo="a"),
            fato_em(fato_valido, "2026-Q2", "9856.4", sufixo="b"),
        ]
        resultado = construir_series(fatos, PERIODOS)
        assert not any(p.tipo is Gatilho.CONFLITO for p in resultado.pendencias)


class TestConfianca:
    def test_confianca_da_serie_e_a_pior_das_pontas(self, fato_valido):
        fatos = [
            fato_em(fato_valido, "2025-Q4", "1.0", sufixo="a", confianca=Confianca.ALTA),
            fato_em(
                fato_valido,
                "2026-Q2",
                "2.0",
                sufixo="b",
                confianca=Confianca.BAIXA,
                flags=(Gatilho.CONFIANCA_BAIXA,),
                revisao_humana=True,
            ),
        ]
        serie = construir_series(fatos, PERIODOS).series[0]
        assert serie.confianca_minima is Confianca.BAIXA
        assert serie.revisao_humana is True

    def test_sem_fatos_nao_ha_series(self):
        assert construir_series([], PERIODOS).series == ()
