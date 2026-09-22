"""Vocabulários controlados. Valor fora da lista é erro, não extensão informal."""

import pytest

from magalu_releases.vocabularios import (
    Base,
    Confianca,
    Gatilho,
    Periodicidade,
    ResultadoCheck,
    Segmento,
    Severidade,
    TipoDocumento,
    TipoValor,
    pior_confianca,
)


class TestVocabularios:
    def test_segmentos_cobrem_as_distincoes_exigidas(self):
        esperados = {
            "consolidado",
            "lojas_fisicas",
            "ecommerce",
            "marketplace",
            "1p",
            "3p",
            "servicos",
            "outro",
        }
        assert {s.value for s in Segmento} == esperados

    def test_base_permite_indefinido(self):
        """'indefinido' existe para não forçar escolha entre ajustado e reportado."""
        assert {b.value for b in Base} == {"reportado", "ajustado", "indefinido"}

    def test_periodicidades(self):
        assert {p.value for p in Periodicidade} == {"trimestre", "acumulado", "anual"}

    def test_tipo_valor_separa_percentual_de_ponto_percentual(self):
        valores = {t.value for t in TipoValor}
        assert "percentual" in valores
        assert "variacao_pp" in valores
        assert "variacao_pct" in valores
        assert TipoValor.PERCENTUAL is not TipoValor.VARIACAO_PP

    def test_existem_dez_gatilhos_de_revisao(self):
        assert len(list(Gatilho)) == 10

    def test_tipo_documento_nao_inclui_por_eliminacao(self):
        valores = {t.value for t in TipoDocumento}
        assert "release_resultados" in valores
        assert "nao_classificado" in valores


class TestConfianca:
    def test_ordem(self):
        assert Confianca.BAIXA < Confianca.MEDIA < Confianca.ALTA

    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ((Confianca.ALTA, Confianca.BAIXA), Confianca.BAIXA),
            ((Confianca.ALTA, Confianca.MEDIA), Confianca.MEDIA),
            ((Confianca.ALTA, Confianca.ALTA), Confianca.ALTA),
            ((Confianca.MEDIA, Confianca.BAIXA, Confianca.ALTA), Confianca.BAIXA),
        ],
    )
    def test_pior_confianca(self, entrada, esperado):
        assert pior_confianca(*entrada) is esperado

    def test_pior_confianca_sem_argumentos_e_erro(self):
        with pytest.raises(ValueError):
            pior_confianca()


class TestEnumsDeSaida:
    def test_severidade(self):
        assert {s.value for s in Severidade} == {"alta", "media", "baixa"}

    def test_resultado_check(self):
        assert {r.value for r in ResultadoCheck} == {"PASS", "FAIL", "ALERTA"}
