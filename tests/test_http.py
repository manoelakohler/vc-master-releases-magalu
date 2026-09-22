"""Cliente HTTP: a única fronteira de rede do projeto.

O spike da etapa 1 mostrou que o edge (WAF Azion) exige conjunto completo de
cabeçalhos de navegador e aplica rate limiting por IP. Educação com o site não é
cortesia opcional aqui — é o que faz a coleta funcionar.

Nenhum teste deste arquivo toca a rede.
"""

import pytest

from magalu_releases.config import carregar_config
from magalu_releases.fonte.http import ClienteHttp, FalhaHttp, Resposta


class RespostaFalsa:
    def __init__(self, status, conteudo=b"ok", url="https://exemplo/", content_type="text/html"):
        self.status_code = status
        self.content = conteudo
        self.url = url
        self.headers = {"Content-Type": content_type}


class SessaoFalsa:
    """Substitui `requests.Session` e registra o que foi pedido."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.chamadas.append({"url": url, **kwargs})
        return self.respostas.pop(0) if self.respostas else RespostaFalsa(200)


@pytest.fixture
def cfg_http():
    return carregar_config().http


def construir(cfg, respostas):
    dormidas = []
    cliente = ClienteHttp(
        cfg,
        sessao=SessaoFalsa(respostas),
        dormir=dormidas.append,
        agora=lambda: 0.0,
    )
    return cliente, dormidas


class TestCabecalhos:
    def test_envia_o_conjunto_completo(self, cfg_http):
        cliente, _ = construir(cfg_http, [RespostaFalsa(200)])
        cliente.obter("https://exemplo/")
        enviados = cliente.sessao.headers
        for obrigatorio in ("User-Agent", "Accept-Language", "Sec-Fetch-Mode", "sec-ch-ua"):
            assert obrigatorio in enviados

    def test_referer_e_repassado(self, cfg_http):
        cliente, _ = construir(cfg_http, [RespostaFalsa(200)])
        cliente.obter("https://exemplo/pagina", referer="https://exemplo/")
        assert cliente.sessao.chamadas[0]["headers"]["Referer"] == "https://exemplo/"


class TestSucesso:
    def test_devolve_resposta_tipada(self, cfg_http):
        cliente, _ = construir(cfg_http, [RespostaFalsa(200, b"<html>")])
        r = cliente.obter("https://exemplo/")
        assert isinstance(r, Resposta)
        assert r.status == 200
        assert r.conteudo == b"<html>"


class TestRetentativa:
    def test_retenta_status_bloqueante_e_depois_passa(self, cfg_http):
        cliente, dormidas = construir(
            cfg_http, [RespostaFalsa(403), RespostaFalsa(503), RespostaFalsa(200, b"ok")]
        )
        r = cliente.obter("https://exemplo/")
        assert r.status == 200
        assert len(cliente.sessao.chamadas) == 3

    def test_backoff_cresce(self, cfg_http):
        cliente, _ = construir(
            cfg_http, [RespostaFalsa(503), RespostaFalsa(503), RespostaFalsa(200)]
        )
        cliente.obter("https://exemplo/")
        assert len(cliente.esperas_backoff) == 2
        assert cliente.esperas_backoff[1] > cliente.esperas_backoff[0]

    def test_backoff_fica_registrado_para_auditoria(self, cfg_http):
        cliente, _ = construir(cfg_http, [RespostaFalsa(403), RespostaFalsa(200)])
        cliente.obter("https://exemplo/")
        assert cliente.esperas_backoff == [cfg_http.backoff_base_segundos]

    def test_desiste_com_erro_explicito(self, cfg_http):
        respostas = [RespostaFalsa(503)] * (cfg_http.tentativas_maximas + 2)
        cliente, _ = construir(cfg_http, respostas)
        with pytest.raises(FalhaHttp) as exc:
            cliente.obter("https://exemplo/")
        assert "503" in str(exc.value)

    def test_nao_retenta_404(self, cfg_http):
        """404 não é bloqueio: insistir só castiga o site."""
        cliente, _ = construir(cfg_http, [RespostaFalsa(404)])
        with pytest.raises(FalhaHttp):
            cliente.obter("https://exemplo/inexistente")
        assert len(cliente.sessao.chamadas) == 1


class TestEducacaoComOSite:
    def test_respeita_intervalo_entre_requisicoes(self, cfg_http):
        relogio = {"t": 0.0}
        dormidas = []

        def dormir(s):
            dormidas.append(s)
            relogio["t"] += s

        cliente = ClienteHttp(
            cfg_http,
            sessao=SessaoFalsa([RespostaFalsa(200), RespostaFalsa(200)]),
            dormir=dormir,
            agora=lambda: relogio["t"],
        )
        cliente.obter("https://exemplo/a")
        cliente.obter("https://exemplo/b")
        assert any(d >= cfg_http.intervalo_entre_requisicoes * 0.9 for d in dormidas)

    def test_primeira_requisicao_nao_espera(self, cfg_http):
        cliente, dormidas = construir(cfg_http, [RespostaFalsa(200)])
        cliente.obter("https://exemplo/")
        assert all(d == 0 for d in dormidas)
