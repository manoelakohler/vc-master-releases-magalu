"""Período fiscal: o release do 4T sai no ano seguinte.

Ordenar por data de publicação embaralha a série e o resultado continua
parecendo uma lista ordenada — por isso a ordenação é por período fiscal.
"""

import pytest

from magalu_releases.periodos import (
    PeriodoFiscal,
    PeriodoIndeterminado,
    interpretar_periodo,
    ordenar_periodos,
)
from magalu_releases.vocabularios import Periodicidade


class TestNotacaoTrimestral:
    @pytest.mark.parametrize(
        "texto,ano,trimestre",
        [
            ("1T25", 2025, 1),
            ("2T25", 2025, 2),
            ("3T25", 2025, 3),
            ("4T25", 2025, 4),
            ("1T2025", 2025, 1),
            ("2T 25", 2025, 2),
            ("2Q25", 2025, 2),
            ("Q2 2025", 2025, 2),
            ("2T26", 2026, 2),
        ],
    )
    def test_interpreta_trimestre(self, texto, ano, trimestre):
        p = interpretar_periodo(texto)
        assert p.ano == ano
        assert p.trimestre == trimestre
        assert p.periodicidade is Periodicidade.TRIMESTRE

    def test_canonico_e_ordenavel(self):
        assert interpretar_periodo("2T25").canonico == "2025-Q2"

    def test_rotulo_preserva_a_grafia_do_documento(self):
        assert interpretar_periodo("2T25").rotulo == "2T25"
        assert interpretar_periodo("Q2 2025").rotulo == "Q2 2025"

    @pytest.mark.parametrize("texto,ano", [("1T09", 2009), ("3T19", 2019), ("4T26", 2026)])
    def test_ano_de_dois_digitos_e_sempre_seculo_21(self, texto, ano):
        assert interpretar_periodo(texto).ano == ano


class TestAcumuladoEAnual:
    @pytest.mark.parametrize(
        "texto,ano,periodicidade,canonico",
        [
            ("6M25", 2025, Periodicidade.ACUMULADO, "2025-6M"),
            ("9M25", 2025, Periodicidade.ACUMULADO, "2025-9M"),
            ("1S25", 2025, Periodicidade.ACUMULADO, "2025-6M"),
            ("12M25", 2025, Periodicidade.ANUAL, "2025-FY"),
        ],
    )
    def test_interpreta_acumulado_e_anual(self, texto, ano, periodicidade, canonico):
        p = interpretar_periodo(texto)
        assert p.ano == ano
        assert p.periodicidade is periodicidade
        assert p.canonico == canonico

    def test_acumulado_nao_tem_trimestre(self):
        assert interpretar_periodo("9M25").trimestre is None


class TestOrdenacao:
    def test_ordem_crescente_por_periodo_fiscal(self):
        entrada = [interpretar_periodo(t) for t in ["3T25", "1T25", "4T24", "2T25"]]
        assert [p.canonico for p in ordenar_periodos(entrada)] == [
            "2024-Q4",
            "2025-Q1",
            "2025-Q2",
            "2025-Q3",
        ]

    def test_virada_de_ano_nao_embaralha(self):
        entrada = [interpretar_periodo(t) for t in ["1T26", "4T25", "3T25"]]
        assert [p.canonico for p in ordenar_periodos(entrada)] == [
            "2025-Q3",
            "2025-Q4",
            "2026-Q1",
        ]

    def test_quarto_trimestre_vem_antes_do_primeiro_do_ano_seguinte(self):
        assert interpretar_periodo("4T25") < interpretar_periodo("1T26")

    def test_mais_recentes_sao_o_final_da_lista(self):
        entrada = [interpretar_periodo(t) for t in ["1T25", "2T26", "3T25"]]
        assert ordenar_periodos(entrada)[-1].canonico == "2026-Q2"


class TestIndeterminado:
    @pytest.mark.parametrize(
        "texto",
        ["", "release", "resultados do período", "5T25", "0T25", "1T", "T25", None],
    )
    def test_nao_chuta_periodo(self, texto):
        """Documento sem período determinável vira pendência, não palpite."""
        with pytest.raises(PeriodoIndeterminado):
            interpretar_periodo(texto)


class TestIgualdadeEHash:
    def test_mesmo_periodo_em_grafias_diferentes_e_igual(self):
        assert interpretar_periodo("2T25").canonico == interpretar_periodo("2T2025").canonico

    def test_serve_como_chave(self):
        p = interpretar_periodo("2T25")
        assert isinstance(hash(p), int)
        assert isinstance(p, PeriodoFiscal)
