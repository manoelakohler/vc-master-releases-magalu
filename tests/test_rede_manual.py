"""Validação real contra a fonte oficial. NÃO roda por padrão.

Desativado pelo marcador `rede` porque teste automatizado não toca a internet
(regra do CLAUDE.md). Existe para a etapa de validação real controlada, quando
alguém quiser confirmar, contra o site de verdade, que a descoberta ainda
funciona depois de um redesenho da Central.

    .venv\\Scripts\\python.exe -m pytest -m rede -v

O site fica atrás do WAF da Azion, com rate limiting por IP. Se estes testes
falharem com 503 logo na primeira requisição, muito provavelmente o IP está em
janela de bloqueio — espere antes de repetir, em vez de insistir.

A navegação é em dois passos porque a URL da Central carrega um token de canal:
home → link da Central → listagem.
"""

import pytest

from magalu_releases.config import carregar_config
from magalu_releases.fonte.descoberta import (
    descobrir_documentos,
    encontrar_url_central,
    tem_paginacao,
)
from magalu_releases.fonte.http import ClienteHttp
from magalu_releases.vocabularios import TipoDocumento

pytestmark = pytest.mark.rede


@pytest.fixture(scope="module")
def central():
    cfg = carregar_config()
    cliente = ClienteHttp(cfg.http)
    home = cliente.obter(cfg.fonte.base_url)
    url = encontrar_url_central(
        home.conteudo.decode("utf-8", "replace"), base_url=cfg.fonte.base_url
    )
    resposta = cliente.obter(url, referer=cfg.fonte.base_url)
    return cfg, resposta.conteudo.decode("utf-8", "replace"), url


def test_home_leva_a_central(central):
    cfg, _, url = central
    assert cfg.fonte.dominio_oficial in url
    assert "?=" in url, "a Central passou a ser servida sem token de canal"


def test_central_responde(central):
    _, html, _ = central
    assert len(html) > 1000


def test_encontra_releases(central):
    cfg, html, _ = central
    documentos = descobrir_documentos(html, base_url=cfg.fonte.base_url)
    releases = [d for d in documentos if d.tipo is TipoDocumento.RELEASE_RESULTADOS]
    assert releases, "nenhum release identificado — a Central pode ter mudado de estrutura"


def test_releases_tem_periodo(central):
    cfg, html, _ = central
    documentos = descobrir_documentos(html, base_url=cfg.fonte.base_url)
    releases = [d for d in documentos if d.tipo is TipoDocumento.RELEASE_RESULTADOS]
    sem_periodo = [d for d in releases if d.periodo is None]
    assert not sem_periodo, f"{len(sem_periodo)} release(s) sem período determinável"


def test_trimestre_do_id_bate_com_o_rotulo(central):
    """Duas declarações do markup sobre o mesmo documento precisam concordar."""
    cfg, html, _ = central
    for d in descobrir_documentos(html, base_url=cfg.fonte.base_url):
        if d.periodo and d.trimestre_declarado is not None:
            assert d.trimestre_declarado == d.periodo.trimestre, d.url_origem


def test_itr_nao_vira_release(central):
    cfg, html, _ = central
    for d in descobrir_documentos(html, base_url=cfg.fonte.base_url):
        if "itr" in (d.titulo or "").lower():
            assert d.tipo is not TipoDocumento.RELEASE_RESULTADOS


def test_relata_cobertura(central):
    cfg, html, _ = central
    documentos = descobrir_documentos(html, base_url=cfg.fonte.base_url)
    releases = [d for d in documentos if d.tipo is TipoDocumento.RELEASE_RESULTADOS]
    periodos = sorted({d.periodo.canonico for d in releases if d.periodo})
    print(f"\nreleases na primeira página: {len(releases)}")
    print(f"períodos: {periodos[0]} .. {periodos[-1]}" if periodos else "nenhum período")
    print(f"paginação por postback detectada: {tem_paginacao(html)}")
