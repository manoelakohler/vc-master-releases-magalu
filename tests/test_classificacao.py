"""Classificação de documentos da Central.

O critério é positivo: o documento precisa se identificar como release. Incluir
um ITR por eliminação contamina a comparação inteira, porque a estrutura dos
números é diferente — e o estrago fica invisível na planilha.
"""

import pytest

from magalu_releases.fonte.classificacao import (
    classificar_documento,
    classificar_por_identificador,
    confirmar_release,
    trimestre_do_identificador,
)
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


class TestClassificacaoPeloIdentificador:
    """Na Central o tipo do documento mora no `id` do controle ASP.NET.

    O link é opaco (`Download.aspx?Arquivo=<token>`) e a âncora diz só "PDF".
    O `id` — `..._linkArq_Release1T_0` — é a única declaração do servidor, no
    markup, sobre o que aquele arquivo é. Sem ele sobra a posição na linha, e
    deduzir tipo de documento por posição é adivinhar.
    """

    PREFIXO = "ContentInternal_ContentPlaceHolderConteudo_rptResultados_linkArq_"

    @pytest.mark.parametrize(
        "sufixo, esperado",
        [
            ("Release1T_0", TD.RELEASE_RESULTADOS),
            ("Release4T_12", TD.RELEASE_RESULTADOS),
            ("ITR1T_0", TD.ITR_DFP),
            ("Apresentacao2T_3", TD.APRESENTACAO),
            ("Audio3T_7", TD.AUDIO_TELECONFERENCIA),
            ("Transcricao4T_9", TD.TRANSCRICAO),
        ],
    )
    def test_reconhece_os_tipos_da_central(self, sufixo, esperado):
        assert classificar_por_identificador(self.PREFIXO + sufixo) is esperado

    def test_identificador_desconhecido_nao_vira_release(self):
        assert classificar_por_identificador(self.PREFIXO + "Novidade1T_0") is (
            TD.NAO_CLASSIFICADO
        )

    def test_identificador_vazio_nao_vira_release(self):
        assert classificar_por_identificador("") is TD.NAO_CLASSIFICADO
        assert classificar_por_identificador(None) is TD.NAO_CLASSIFICADO

    def test_extrai_o_trimestre_do_identificador(self):
        assert trimestre_do_identificador(self.PREFIXO + "Release3T_5") == 3

    def test_trimestre_ausente_e_none(self):
        assert trimestre_do_identificador("qualquer_coisa") is None


class TestConfirmacaoPeloNomeDoServidor:
    """O download traz, de graça, a declaração do servidor sobre o arquivo.

    `Content-Disposition: filename="MGLU_ER_1T26_POR.pdf"` confirma tipo e
    período sem nenhuma requisição extra. Confirmação que não bate não é
    detalhe: significa que o token da Central aponta para outro documento.
    """

    def test_release_do_periodo_esperado_confirma(self):
        ok, motivo = confirmar_release("MGLU_ER_1T26_POR.pdf", "1T26")
        assert ok is True
        assert motivo is None

    def test_periodo_divergente_nao_confirma(self):
        ok, motivo = confirmar_release("MGLU_ER_4T25_POR.pdf", "1T26")
        assert ok is False
        assert "4T25" in motivo and "1T26" in motivo

    def test_outro_tipo_de_documento_nao_confirma(self):
        ok, motivo = confirmar_release(
            "1T26 - Demonstrações Financeiras (DFS) - Magalu.pdf", "1T26"
        )
        assert ok is False
        assert motivo

    def test_transcricao_da_teleconferencia_nao_confirma(self):
        ok, motivo = confirmar_release("MGLU_Call_1T26_POR.pdf", "1T26")
        assert ok is False

    def test_servidor_sem_nome_nao_confirma_mas_explica(self):
        ok, motivo = confirmar_release(None, "1T26")
        assert ok is False
        assert "não nomeou" in motivo

    def test_nome_por_extenso_tambem_confirma(self):
        ok, _ = confirmar_release("Release de Resultados 1T26.pdf", "1T26")
        assert ok is True
