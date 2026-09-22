"""Classificação de documentos da Central.

O critério é positivo: o documento precisa se identificar como release. Incluir
um ITR por eliminação contamina a comparação inteira, porque a estrutura dos
números é diferente — e o estrago fica invisível na planilha.
"""

import pytest

from magalu_releases.fonte.classificacao import classificar_documento
from magalu_releases.vocabularios import TipoDocumento as TD


class TestReleaseAceito:
    @pytest.mark.parametrize(
        "titulo",
        [
            "Release de Resultado",
            "Release de Resultados 2T25",
            "Divulgação de Resultados - 1T26",
            "Earnings Release 4T25",
            "Release de Resultados do 3T25 (PDF)",
            "RELEASE DE RESULTADO",
        ],
    )
    def test_identifica_release(self, titulo):
        assert classificar_documento(titulo) is TD.RELEASE_RESULTADOS


class TestExcluidos:
    @pytest.mark.parametrize(
        "titulo,esperado",
        [
            ("ITR", TD.ITR_DFP),
            ("ITR 2T25", TD.ITR_DFP),
            ("Informações Trimestrais - ITR", TD.ITR_DFP),
            ("DFP 2025", TD.ITR_DFP),
            ("Demonstrações Financeiras Padronizadas", TD.ITR_DFP),
            ("Demonstrações Financeiras", TD.DEMONSTRACOES_FINANCEIRAS),
            ("Apresentação de Resultados", TD.APRESENTACAO),
            ("Apresentação 2T25", TD.APRESENTACAO),
            ("Transcrição da Teleconferência", TD.TRANSCRICAO),
            ("Transcrição 1T26", TD.TRANSCRICAO),
            ("Áudio da Teleconferência", TD.AUDIO_TELECONFERENCIA),
            ("Teleconferência de Resultados", TD.AUDIO_TELECONFERENCIA),
            ("Webcast de Resultados", TD.AUDIO_TELECONFERENCIA),
            ("Fato Relevante", TD.FATO_RELEVANTE),
            ("Comunicado ao Mercado", TD.COMUNICADO),
            ("Aviso aos Acionistas", TD.COMUNICADO),
            ("Ata de Reunião do Conselho", TD.COMUNICADO),
            ("Formulário de Referência", TD.FORMULARIO_REFERENCIA),
            ("Relatório de Sustentabilidade 2025", TD.SUSTENTABILIDADE),
            ("Planilha de Resultados", TD.PLANILHA),
            ("Spreadsheet 2T25", TD.PLANILHA),
        ],
    )
    def test_nao_e_release(self, titulo, esperado):
        assert classificar_documento(titulo) is esperado
        assert classificar_documento(titulo) is not TD.RELEASE_RESULTADOS


class TestArmadilhas:
    def test_apresentacao_de_resultados_nao_vira_release(self):
        """Contém 'Resultados', mas apresentação é slide, não release."""
        assert classificar_documento("Apresentação de Resultados 2T25") is TD.APRESENTACAO

    def test_transcricao_de_resultados_nao_vira_release(self):
        assert classificar_documento("Transcrição da Teleconferência de Resultados") is (
            TD.TRANSCRICAO
        )

    def test_planilha_de_resultados_nao_vira_release(self):
        assert classificar_documento("Planilha de Resultados 2T25") is TD.PLANILHA


class TestNaoClassificado:
    @pytest.mark.parametrize(
        "titulo", ["", "   ", "Documento", "Arquivo 2T25", "PDF", "Clique aqui", None]
    )
    def test_nunca_inclui_por_eliminacao(self, titulo):
        assert classificar_documento(titulo) is TD.NAO_CLASSIFICADO

    def test_nao_classificado_nao_e_release(self):
        assert classificar_documento("Documento sem rótulo") is not TD.RELEASE_RESULTADOS


class TestContextoAuxiliar:
    def test_usa_a_url_quando_o_titulo_e_generico(self):
        tipo = classificar_documento("Clique aqui", url="https://x/releases/release-2t25.pdf")
        assert tipo is TD.RELEASE_RESULTADOS

    def test_titulo_explicito_tem_prioridade_sobre_a_url(self):
        tipo = classificar_documento("Apresentação", url="https://x/release-2t25.pdf")
        assert tipo is TD.APRESENTACAO
