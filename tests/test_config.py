"""Configuração é ponto único: se o código duplicar um valor daqui, vira defeito."""

import pytest

from magalu_releases.config import Config, carregar_config


def test_carrega_config_padrao():
    cfg = carregar_config()
    assert isinstance(cfg, Config)


def test_fonte_e_o_dominio_oficial():
    cfg = carregar_config()
    assert cfg.fonte.dominio_oficial == "ri.magazineluiza.com.br"
    assert cfg.fonte.url_central.startswith("https://ri.magazineluiza.com.br")


def test_cabecalhos_http_completos():
    """O WAF rejeita clientes sem o conjunto completo — ver spike da etapa 1."""
    cfg = carregar_config()
    obrigatorios = {
        "User-Agent",
        "Accept",
        "Accept-Language",
        "Accept-Encoding",
        "Sec-Fetch-Dest",
        "Sec-Fetch-Mode",
        "Sec-Fetch-Site",
        "sec-ch-ua",
        "sec-ch-ua-platform",
    }
    assert obrigatorios <= set(cfg.http.cabecalhos)


def test_politica_de_educacao_com_o_site():
    cfg = carregar_config()
    assert cfg.http.intervalo_entre_requisicoes >= 1.0
    assert cfg.http.tentativas_maximas >= 2
    assert 403 in cfg.http.status_para_retentar
    assert 503 in cfg.http.status_para_retentar


def test_n_padrao_existe_mas_nao_e_imposto():
    cfg = carregar_config()
    assert cfg.execucao.n_padrao >= 1


def test_config_e_imutavel():
    """Configuração mutável em tempo de execução reintroduz valor espalhado."""
    cfg = carregar_config()
    with pytest.raises(Exception):
        cfg.fonte.url_central = "https://exemplo.invalido/"
