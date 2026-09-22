"""Descoberta dos documentos na Central de Resultados.

A leitura é por âncora, na ordem do documento, associando cada link ao último
período visto. Isso sobrevive a mudanças de markup melhor que seletores CSS
fixos — e sites de RI mudam de estrutura.
"""

import pytest

from fixtures.central_sintetica import HTML_CENTRAL, HTML_SEM_PERIODO
from magalu_releases.fonte.descoberta import descobrir_documentos
from magalu_releases.vocabularios import TipoDocumento as TD

BASE = "https://ri.magazineluiza.com.br/"


@pytest.fixture
def encontrados():
    return descobrir_documentos(HTML_CENTRAL, base_url=BASE)


class TestDescoberta:
    def test_encontra_todos_os_documentos(self, encontrados):
        assert len(encontrados) >= 13

    def test_urls_ficam_absolutas(self, encontrados):
        assert all(d.url_origem.startswith("https://") for d in encontrados)

    def test_url_relativa_e_resolvida_contra_a_base(self, encontrados):
        alvo = [d for d in encontrados if "release-2t26" in d.url_origem][0]
        assert alvo.url_origem == "https://ri.magazineluiza.com.br/download/release-2t26.pdf"

    def test_ignora_javascript_e_ancoras_de_navegacao(self, encontrados):
        assert not any("javascript:" in d.url_origem for d in encontrados)

    def test_titulo_preserva_o_rotulo_do_site(self, encontrados):
        titulos = {d.titulo for d in encontrados}
        assert "Release de Resultado" in titulos
        assert any("Apresenta" in t for t in titulos)


class TestPeriodo:
    def test_periodo_vem_do_cabecalho_do_grupo(self, encontrados):
        alvo = [d for d in encontrados if "release-2t26" in d.url_origem][0]
        assert alvo.periodo is not None
        assert alvo.periodo.canonico == "2026-Q2"

    def test_cada_grupo_recebe_seu_proprio_periodo(self, encontrados):
        por_url = {d.url_origem.rsplit("/", 1)[-1]: d for d in encontrados}
        assert por_url["release-1t26.pdf"].periodo.canonico == "2026-Q1"
        assert por_url["release-4t25.pdf"].periodo.canonico == "2025-Q4"
        assert por_url["release-3t25.pdf"].periodo.canonico == "2025-Q3"

    def test_periodo_no_proprio_rotulo_tem_prioridade(self, encontrados):
        alvo = [d for d in encontrados if "release-3t25" in d.url_origem][0]
        assert alvo.periodo.canonico == "2025-Q3"

    def test_documento_sem_periodo_fica_sem_periodo(self):
        achados = descobrir_documentos(HTML_SEM_PERIODO, base_url=BASE)
        assert achados[0].periodo is None


class TestClassificacao:
    def test_releases_sao_identificados(self, encontrados):
        releases = [d for d in encontrados if d.tipo is TD.RELEASE_RESULTADOS]
        assert len(releases) == 4

    def test_um_release_por_periodo(self, encontrados):
        releases = [d for d in encontrados if d.tipo is TD.RELEASE_RESULTADOS]
        canonicos = sorted(d.periodo.canonico for d in releases)
        assert canonicos == ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"]

    def test_itr_e_apresentacao_nao_viram_release(self, encontrados):
        for d in encontrados:
            if "itr" in d.url_origem or "apresentacao" in d.url_origem:
                assert d.tipo is not TD.RELEASE_RESULTADOS


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
        from magalu_releases.fonte.descoberta import tem_paginacao

        assert tem_paginacao(HTML_CENTRAL) is True
        assert tem_paginacao(HTML_SEM_PERIODO) is False
