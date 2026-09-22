"""As invariantes do contrato de dados viram teste executável.

Cada uma existe porque a sua violação produz um número plausível e errado na
planilha — o único erro que ninguém percebe.
"""

import pytest

from magalu_releases.models import chave_serie, validar_fato
from magalu_releases.vocabularios import Base, Confianca, Gatilho, Segmento, TipoValor


class TestFatoValido:
    def test_fato_de_referencia_nao_tem_violacao(self, fato_valido):
        assert validar_fato(fato_valido()) == ()

    def test_fato_e_imutavel(self, fato_valido):
        f = fato_valido()
        with pytest.raises(Exception):
            f.valor_normalizado = 1.0


class TestEvidenciaObrigatoria:
    """Um fato sem documento, página e trecho não é fato — é suposição."""

    @pytest.mark.parametrize(
        "campo,valor",
        [("documento_id", ""), ("trecho_fonte", ""), ("pagina", 0), ("pagina", -1)],
    )
    def test_evidencia_incompleta_e_violacao(self, fato_valido, campo, valor):
        assert validar_fato(fato_valido(**{campo: valor})) != ()

    def test_trecho_precisa_conter_o_valor_original(self, fato_valido):
        f = fato_valido(trecho_fonte="Receita Líquida 1.111,1")
        violacoes = validar_fato(f)
        assert any("trecho" in v.lower() for v in violacoes)

    def test_valor_original_nunca_vazio(self, fato_valido):
        assert validar_fato(fato_valido(valor_original="", trecho_fonte="qualquer")) != ()


class TestNuloNuncaEZero:
    def test_unidade_ausente_exige_normalizado_nulo(self, fato_valido):
        f = fato_valido(unidade=None, valor_normalizado=9856.4)
        violacoes = validar_fato(f)
        assert any("unidade" in v.lower() for v in violacoes)

    def test_unidade_ausente_com_normalizado_nulo_e_valido(self, fato_valido):
        f = fato_valido(unidade=None, valor_normalizado=None, motivo="unidade não clara")
        assert validar_fato(f) == ()

    def test_zero_e_valor_legitimo(self, fato_valido):
        f = fato_valido(valor_original="0,0", valor_normalizado=0.0, trecho_fonte="Linha 0,0")
        assert validar_fato(f) == ()


class TestRevisaoHumana:
    def test_flag_exige_revisao_humana(self, fato_valido):
        f = fato_valido(flags=(Gatilho.AMBIGUIDADE,), revisao_humana=False)
        assert validar_fato(f) != ()

    def test_revisao_humana_exige_flag(self, fato_valido):
        f = fato_valido(flags=(), revisao_humana=True)
        assert validar_fato(f) != ()

    def test_confianca_baixa_implica_revisao(self, fato_valido):
        f = fato_valido(confianca=Confianca.BAIXA, flags=(), revisao_humana=False)
        violacoes = validar_fato(f)
        assert any("confian" in v.lower() for v in violacoes)

    def test_confianca_baixa_marcada_corretamente_e_valida(self, fato_valido):
        f = fato_valido(
            confianca=Confianca.BAIXA,
            flags=(Gatilho.CONFIANCA_BAIXA,),
            revisao_humana=True,
            motivo="trecho não isola o valor",
        )
        assert validar_fato(f) == ()

    def test_base_indefinida_exige_pendencia(self, fato_valido):
        """'indefinido' nunca é um estado confortável: sempre acompanha revisão."""
        f = fato_valido(base=Base.INDEFINIDO, flags=(), revisao_humana=False)
        assert validar_fato(f) != ()


class TestChaveDeSerie:
    def test_chave_usa_a_tupla_completa(self, fato_valido):
        assert chave_serie(fato_valido()) == (
            "receita_liquida",
            Segmento.CONSOLIDADO,
            Base.REPORTADO,
            fato_valido().periodicidade,
            TipoValor.ABSOLUTO,
        )

    def test_ajustado_e_reportado_sao_series_diferentes(self, fato_valido):
        assert chave_serie(fato_valido(base=Base.REPORTADO)) != chave_serie(
            fato_valido(base=Base.AJUSTADO)
        )

    def test_segmentos_diferentes_sao_series_diferentes(self, fato_valido):
        assert chave_serie(fato_valido(segmento=Segmento.CONSOLIDADO)) != chave_serie(
            fato_valido(segmento=Segmento.ECOMMERCE)
        )

    def test_percentual_e_absoluto_sao_series_diferentes(self, fato_valido):
        assert chave_serie(fato_valido(tipo_valor=TipoValor.ABSOLUTO)) != chave_serie(
            fato_valido(tipo_valor=TipoValor.PERCENTUAL)
        )


class TestDocumento:
    def test_documento_valido(self, documento_valido):
        d = documento_valido()
        assert d.textual is True
        assert len(d.sha256) == 64

    def test_documento_e_imutavel(self, documento_valido):
        with pytest.raises(Exception):
            documento_valido().titulo = "outro"
