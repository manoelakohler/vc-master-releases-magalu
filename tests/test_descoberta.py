"""Descoberta dos documentos na Central de Resultados.

A listagem é uma tabela: uma linha por trimestre, o rótulo do período na
primeira célula e links opacos (`Download.aspx?Arquivo=<token>`) cuja âncora diz
apenas "PDF". O tipo do documento é lido do `id` do controle ASP.NET, que é a
única declaração de tipo existente no markup.

A URL da própria Central carrega um token de canal e é descoberta a partir da
home — congelá-la em configuração foi o que produziu HTTP 500 quando o site
mudou de estrutura.
"""

import pytest

from fixtures.central_sintetica import (
    HTML_CENTRAL,
    HTML_HOME,
    HTML_HOME_SEM_CENTRAL,
    HTML_SEM_PERIODO,
)
from magalu_releases.fonte.descoberta import (
    CentralNaoEncontrada,
    descobrir_documentos,
    encontrar_url_central,
    tem_paginacao,
)
from magalu_releases.vocabularios import TipoDocumento as TD

BASE = "https://ri.magazineluiza.com.br/"


@pytest.fixture
def encontrados():
    return descobrir_documentos(HTML_CENTRAL, base_url=BASE)


def release_de(encontrados, rotulo):
    achados = [
        d
        for d in encontrados
        if d.tipo is TD.RELEASE_RESULTADOS and d.periodo and d.periodo.rotulo == rotulo
    ]
    assert achados, f"nenhum release encontrado para {rotulo}"
    return achados[0]


class TestNavegacaoAteACentral:
    def test_encontra_a_url_com_token_na_home(self):
        url = encontrar_url_central(HTML_HOME, base_url=BASE)
        assert url.startswith("https://ri.magazineluiza.com.br/ListResultados/")
        assert "0WX0bwP76pYcZvx+vXUnvg==" in url

    def test_home_sem_o_link_falha_alto(self):
        """Sem a Central não há fonte oficial — e não se inventa uma URL."""
        with pytest.raises(CentralNaoEncontrada):
            encontrar_url_central(HTML_HOME_SEM_CENTRAL, base_url=BASE)


class TestDescoberta:
    def test_encontra_os_arquivos_de_cada_periodo(self, encontrados):
        assert len(encontrados) == 4 * 5

    def test_urls_ficam_absolutas(self, encontrados):
        assert all(d.url_origem.startswith("https://") for d in encontrados)

    def test_ignora_javascript_e_navegacao(self, encontrados):
        assert not any("javascript:" in d.url_origem for d in encontrados)
        assert not any("ShowResultado" in d.url_origem for d in encontrados)

    def test_titulo_amarra_periodo_e_tipo_do_markup(self, encontrados):
        assert release_de(encontrados, "1T26").titulo == "1T26 · Release"


class TestPeriodo:
    def test_periodo_vem_da_primeira_celula_da_linha(self, encontrados):
        assert release_de(encontrados, "2T26").periodo.canonico == "2026-Q2"

    def test_cada_linha_recebe_seu_proprio_periodo(self, encontrados):
        canonicos = sorted(
            d.periodo.canonico for d in encontrados if d.tipo is TD.RELEASE_RESULTADOS
        )
        assert canonicos == ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]

    def test_linha_sem_rotulo_fica_sem_periodo(self):
        achados = descobrir_documentos(HTML_SEM_PERIODO, base_url=BASE)
        assert achados and all(d.periodo is None for d in achados)

    def test_trimestre_do_id_confere_com_o_rotulo(self, encontrados):
        """O id diz `Release3T`; a célula diz `3T25`. Discordância é sinal de erro."""
        for d in encontrados:
            if d.periodo and d.trimestre_declarado is not None:
                assert d.trimestre_declarado == d.periodo.trimestre


class TestClassificacaoPeloMarkup:
    def test_um_release_por_periodo(self, encontrados):
        releases = [d for d in encontrados if d.tipo is TD.RELEASE_RESULTADOS]
        assert len(releases) == 4

    def test_itr_apresentacao_audio_e_transcricao_nao_viram_release(self, encontrados):
        tipos = {d.tipo for d in encontrados}
        assert TD.ITR_DFP in tipos
        assert TD.APRESENTACAO in tipos
        assert TD.AUDIO_TELECONFERENCIA in tipos
        assert TD.TRANSCRICAO in tipos

    def test_ancora_diz_apenas_pdf_e_ainda_assim_classifica(self, encontrados):
        """O texto do link não distingue nada: quem distingue é o id."""
        assert all(d.tipo is not TD.NAO_CLASSIFICADO for d in encontrados)


class TestIdentificadores:
    def test_documento_id_e_unico(self, encontrados):
        ids = [d.documento_id for d in encontrados]
        assert len(ids) == len(set(ids))

    def test_documento_id_e_estavel_entre_execucoes(self):
        a = descobrir_documentos(HTML_CENTRAL, base_url=BASE)
        b = descobrir_documentos(HTML_CENTRAL, base_url=BASE)
        assert [d.documento_id for d in a] == [d.documento_id for d in b]


class TestPaginacao:
    def test_sinaliza_paginacao_por_postback(self):
        assert tem_paginacao(HTML_CENTRAL) is True
        assert tem_paginacao(HTML_SEM_PERIODO) is False
