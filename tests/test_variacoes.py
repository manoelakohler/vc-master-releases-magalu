"""Cálculo e supressão de variações.

Supressão não é falta de recurso: uma variação calculada sobre base frágil
parece tão sólida quanto qualquer outra na planilha, e é isso que a torna
perigosa.
"""

import pytest

from magalu_releases.analise.variacoes import calcular_variacoes
from magalu_releases.models import PontoSerie, Serie
from magalu_releases.vocabularios import (
    Base,
    BaseComparacao,
    Confianca,
    Periodicidade,
    Segmento,
    TipoValor,
)

PERIODOS = ["2025-Q4", "2026-Q1", "2026-Q2"]


def serie(valores, tipo_valor=TipoValor.ABSOLUTO, confianca=Confianca.ALTA, unidade="R$ milhões"):
    pontos = tuple(
        PontoSerie(
            periodo_canonico=c,
            fato_id=("f-" + c) if v is not None else None,
            valor_normalizado=v,
            valor_original=str(v) if v is not None else None,
        )
        for c, v in zip(PERIODOS, valores)
    )
    return Serie(
        serie_id="s-1",
        metrica_id="receita_liquida",
        metrica_rotulo="Receita Líquida",
        segmento=Segmento.CONSOLIDADO,
        base=Base.REPORTADO,
        periodicidade=Periodicidade.TRIMESTRE,
        tipo_valor=tipo_valor,
        unidade_serie=unidade,
        pontos=pontos,
        confianca_minima=confianca,
    )


class TestCalculoBasico:
    def test_variacao_absoluta_e_percentual(self):
        v = calcular_variacoes(serie([100.0, 110.0, 121.0]))
        assert v[0].variacao_abs == pytest.approx(10.0)
        assert v[0].variacao_pct == pytest.approx(10.0)
        assert v[1].variacao_pct == pytest.approx(10.0)

    def test_uma_variacao_por_par_consecutivo(self):
        assert len(calcular_variacoes(serie([1.0, 2.0, 3.0]))) == 2

    def test_base_de_comparacao_e_declarada(self):
        v = calcular_variacoes(serie([100.0, 110.0, 121.0]))
        assert all(x.base_comparacao is BaseComparacao.PERIODO_ANTERIOR for x in v)

    def test_variacao_negativa(self):
        v = calcular_variacoes(serie([100.0, 80.0, 80.0]))
        assert v[0].variacao_abs == pytest.approx(-20.0)
        assert v[0].variacao_pct == pytest.approx(-20.0)


class TestPontoPercentual:
    def test_percentual_usa_pontos_percentuais(self):
        s = serie([26.1, 27.6, 28.4], tipo_valor=TipoValor.PERCENTUAL, unidade="%")
        v = calcular_variacoes(s)
        assert v[0].variacao_pp == pytest.approx(1.5)
        assert v[1].variacao_pp == pytest.approx(0.8)

    def test_percentual_nunca_produz_variacao_percentual(self):
        s = serie([10.0, 12.0, 12.0], tipo_valor=TipoValor.PERCENTUAL, unidade="%")
        assert all(x.variacao_pct is None for x in calcular_variacoes(s))

    def test_dez_para_doze_e_dois_pp_nao_vinte_porcento(self):
        s = serie([10.0, 12.0, 12.0], tipo_valor=TipoValor.PERCENTUAL, unidade="%")
        v = calcular_variacoes(s)
        assert v[0].variacao_pp == pytest.approx(2.0)
        assert v[0].variacao_pct is None

    def test_absoluto_nunca_produz_pp(self):
        assert all(x.variacao_pp is None for x in calcular_variacoes(serie([100.0, 110.0, 121.0])))


class TestSupressao:
    def test_denominador_zero_nao_calcula_percentual(self):
        v = calcular_variacoes(serie([0.0, 50.0, 60.0]))
        assert v[0].variacao_pct is None
        assert v[0].motivo_nao_calculada
        assert v[0].variacao_abs == pytest.approx(50.0)

    def test_denominador_zero_nao_vira_zero_nem_infinito(self):
        v = calcular_variacoes(serie([0.0, 50.0, 60.0]))
        assert v[0].variacao_pct is None

    def test_confianca_baixa_suprime_a_variacao(self):
        v = calcular_variacoes(serie([100.0, 110.0, 121.0], confianca=Confianca.BAIXA))
        assert all(x.calculada is False for x in v)
        assert all(x.motivo_nao_calculada for x in v)

    def test_ponta_ausente_suprime(self):
        v = calcular_variacoes(serie([100.0, None, 121.0]))
        assert v[0].calculada is False
        assert v[1].calculada is False
        assert all(x.motivo_nao_calculada for x in v)

    def test_texto_nao_tem_variacao_numerica(self):
        v = calcular_variacoes(serie([1.0, 2.0, 3.0], tipo_valor=TipoValor.TEXTO))
        assert all(x.calculada is False for x in v)
        assert all(x.variacao_abs is None and x.variacao_pct is None for x in v)

    def test_um_unico_ponto_nao_gera_variacao_calculada(self):
        v = calcular_variacoes(serie([None, None, 10.0]))
        assert all(x.calculada is False for x in v)


class TestIntegridade:
    def test_nunca_compara_series_diferentes(self):
        assert all(x.serie_id == "s-1" for x in calcular_variacoes(serie([100.0, 110.0, 121.0])))

    def test_periodos_da_variacao_sao_consecutivos_e_crescentes(self):
        v = calcular_variacoes(serie([100.0, 110.0, 121.0]))
        assert v[0].periodo_de == "2025-Q4" and v[0].periodo_para == "2026-Q1"
        assert v[1].periodo_de == "2026-Q1" and v[1].periodo_para == "2026-Q2"
