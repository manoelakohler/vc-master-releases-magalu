"""Formato numérico brasileiro.

Inverter separador de milhar e decimal produz erro de fator mil com aparência
plausível. É o erro mais destrutivo do domínio, então é o módulo mais testado.
"""

import pytest

from magalu_releases.numeros import (
    MARCADORES_AUSENCIA,
    ValorInterpretado,
    eh_marcador_ausencia,
    interpretar_valor,
    normalizar_numero_ptbr,
)


class TestFormatoBrasileiro:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("1.234,5", 1234.5),
            ("9.856,4", 9856.4),
            ("12,3", 12.3),
            ("1.234.567", 1234567.0),
            ("1.234.567,89", 1234567.89),
            ("0,0", 0.0),
            ("100", 100.0),
            ("1.000", 1000.0),
            ("36,7", 36.7),
        ],
    )
    def test_ponto_e_milhar_virgula_e_decimal(self, texto, esperado):
        assert normalizar_numero_ptbr(texto) == pytest.approx(esperado)

    def test_mil_duzentos_nao_vira_um_virgula_dois(self):
        """O erro de fator mil: '1.234' são mil duzentos e trinta e quatro."""
        assert normalizar_numero_ptbr("1.234") == 1234.0
        assert normalizar_numero_ptbr("1.234") != 1.234


class TestSinal:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("(1.234,5)", -1234.5),
            ("-1.234,5", -1234.5),
            ("(1.234)", -1234.0),
            ("- 1.234,5", -1234.5),
            ("+2,3", 2.3),
        ],
    )
    def test_parenteses_e_sinal_explicito(self, texto, esperado):
        assert normalizar_numero_ptbr(texto) == pytest.approx(esperado)

    def test_rotulo_de_prejuizo_torna_negativo(self):
        v = interpretar_valor("135,0", unidade_contexto="R$ milhões", rotulo="Prejuízo líquido")
        assert v.normalizado == pytest.approx(-135.0)

    def test_rotulo_de_lucro_nao_mexe_no_sinal(self):
        v = interpretar_valor("135,0", unidade_contexto="R$ milhões", rotulo="Lucro líquido")
        assert v.normalizado == pytest.approx(135.0)

    def test_prejuizo_ja_negativo_nao_inverte_duas_vezes(self):
        v = interpretar_valor("(135,0)", unidade_contexto="R$ milhões", rotulo="Prejuízo líquido")
        assert v.normalizado == pytest.approx(-135.0)


class TestAusencia:
    @pytest.mark.parametrize("marcador", sorted(MARCADORES_AUSENCIA))
    def test_marcadores_sao_reconhecidos(self, marcador):
        assert eh_marcador_ausencia(marcador)

    @pytest.mark.parametrize("texto", ["-", "—", "n.a.", "n/a", "n.d."])
    def test_ausencia_vira_none_e_nunca_zero(self, texto):
        v = interpretar_valor(texto, unidade_contexto="R$ milhões")
        assert v.normalizado is None
        assert v.normalizado != 0
        assert v.motivo is not None

    def test_zero_reportado_continua_zero(self):
        """Zero é valor reportável; confundi-lo com ausência corrompe variações."""
        v = interpretar_valor("0,0", unidade_contexto="R$ milhões")
        assert v.normalizado == 0.0
        assert v.motivo is None


class TestUnidade:
    def test_percentual_e_autoevidente(self):
        v = interpretar_valor("36,7%")
        assert v.normalizado == pytest.approx(36.7)
        assert v.unidade == "%"

    def test_ponto_percentual_nao_e_percentual(self):
        v = interpretar_valor("+2,3 p.p.")
        assert v.unidade == "p.p."
        assert v.unidade != "%"
        assert v.normalizado == pytest.approx(2.3)

    def test_escala_monetaria_sem_contexto_nao_normaliza(self):
        """'R$ 9.856,4' pode ser mil ou milhão. Sem o cabeçalho, não se sabe."""
        v = interpretar_valor("R$ 9.856,4")
        assert v.normalizado is None
        assert v.unidade is None
        assert v.motivo is not None

    def test_escala_vinda_do_contexto_resolve(self):
        v = interpretar_valor("R$ 9.856,4", unidade_contexto="R$ milhões")
        assert v.normalizado == pytest.approx(9856.4)
        assert v.unidade == "R$ milhões"

    def test_escala_explicita_no_proprio_texto(self):
        v = interpretar_valor("R$ 9,9 bilhões")
        assert v.normalizado == pytest.approx(9.9)
        assert v.unidade == "R$ bilhões"

    def test_contagem_precisa_de_contexto(self):
        v = interpretar_valor("1.245", unidade_contexto="lojas")
        assert v.normalizado == pytest.approx(1245.0)
        assert v.unidade == "lojas"


class TestPreservacao:
    def test_original_nunca_e_alterado(self):
        bruto = "  R$ 9.856,4  "
        v = interpretar_valor(bruto, unidade_contexto="R$ milhões")
        assert v.original == bruto

    def test_retorna_tipo_congelado(self):
        v = interpretar_valor("12,3", unidade_contexto="%")
        assert isinstance(v, ValorInterpretado)
        with pytest.raises(Exception):
            v.normalizado = 99.0


class TestEntradasInvalidas:
    @pytest.mark.parametrize("texto", ["abc", "R$", "??", "1.2.3,4,5"])
    def test_texto_nao_numerico_nao_inventa_valor(self, texto):
        v = interpretar_valor(texto, unidade_contexto="R$ milhões")
        assert v.normalizado is None
        assert v.motivo is not None


class TestEscalaMonetaria:
    """Uma série pode mudar de escala entre releases: milhares num, milhões noutro."""

    def test_converte_milhoes_para_mil(self):
        from magalu_releases.numeros import converter_escala

        assert converter_escala(9.8564, "R$ milhões", "R$ mil") == pytest.approx(9856.4)

    def test_converte_mil_para_milhoes(self):
        from magalu_releases.numeros import converter_escala

        assert converter_escala(9856.4, "R$ mil", "R$ milhões") == pytest.approx(9.8564)

    def test_bilhoes_para_milhoes(self):
        from magalu_releases.numeros import converter_escala

        assert converter_escala(9.9, "R$ bilhões", "R$ milhões") == pytest.approx(9900.0)

    def test_mesma_unidade_nao_muda(self):
        from magalu_releases.numeros import converter_escala

        assert converter_escala(123.4, "R$ milhões", "R$ milhões") == pytest.approx(123.4)

    def test_unidade_nao_monetaria_nao_converte(self):
        from magalu_releases.numeros import EscalaIncompativel, converter_escala

        with pytest.raises(EscalaIncompativel):
            converter_escala(12.3, "%", "R$ milhões")

    def test_unidade_desconhecida_nao_converte(self):
        from magalu_releases.numeros import EscalaIncompativel, converter_escala

        with pytest.raises(EscalaIncompativel):
            converter_escala(12.3, "lojas", "R$ milhões")

    def test_conversao_ida_e_volta_preserva(self):
        from magalu_releases.numeros import converter_escala

        ida = converter_escala(9856.4, "R$ mil", "R$ bilhões")
        assert converter_escala(ida, "R$ bilhões", "R$ mil") == pytest.approx(9856.4)
