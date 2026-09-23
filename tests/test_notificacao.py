"""Aviso de conclusão por e-mail.

O envio é a única parte do projeto, além da coleta, que sai para a rede — e
por isso vive atrás de uma fronteira injetável, como o cliente HTTP. Nenhum
teste deste arquivo abre socket: o transporte é substituído por um duplo que
registra o que teria sido enviado.

O corpo é artefato do projeto como qualquer outro: passa pelo mesmo varredor
de linguagem que recusa recomendação de investimento.
"""

import pytest

from magalu_releases.auditoria.checks import (
    varrer_linguagem_promocional,
    varrer_linguagem_recomendacao,
)
from magalu_releases.config import carregar_config
from magalu_releases.saida.notificacao import (
    CredencialAusente,
    EnvioFalhou,
    Mensagem,
    enviar,
    montar_mensagem,
)


class TransporteFalso:
    """Duplo da fronteira SMTP: guarda a mensagem em vez de enviá-la."""

    def __init__(self, erro=None):
        self.erro = erro
        self.enviadas = []

    def __call__(self, mensagem, *, servidor, porta, usar_tls, usuario, senha):
        if self.erro:
            raise self.erro
        self.enviadas.append(
            {"mensagem": mensagem, "servidor": servidor, "porta": porta,
             "usar_tls": usar_tls, "usuario": usuario}
        )


@pytest.fixture
def cfg():
    return carregar_config()


@pytest.fixture
def dados():
    return dict(
        run_id="magalu_N3_2025-Q4-a-2026-Q2_20260917-190000",
        rotulos=("4T25", "1T26", "2T26"),
        n_pedido=3,
        n_obtido=3,
        url_dashboard="https://claude.ai/artifact/abc123",
        verificacoes=33,
        falhas=0,
        pendencias=0,
    )


class TestMensagem:
    def test_assunto_diz_o_que_terminou_e_o_intervalo(self, dados):
        mensagem = montar_mensagem(destinatario="x@y.z", **dados)
        assert "4T25" in mensagem.assunto and "2T26" in mensagem.assunto
        assert "Magalu" in mensagem.assunto or "Magazine Luiza" in mensagem.assunto

    def test_corpo_traz_periodos_auditoria_e_link(self, dados):
        corpo = montar_mensagem(destinatario="x@y.z", **dados).corpo
        assert "4T25, 1T26, 2T26" in corpo
        assert "33" in corpo and "0" in corpo
        assert "https://claude.ai/artifact/abc123" in corpo

    def test_corpo_e_curto(self, dados):
        """Aviso com link, não relatório: cabe na tela sem rolagem."""
        corpo = montar_mensagem(destinatario="x@y.z", **dados).corpo
        assert len(corpo.splitlines()) <= 14

    def test_declara_analise_independente(self, dados):
        corpo = montar_mensagem(destinatario="x@y.z", **dados).corpo
        assert "independente" in corpo.lower()

    def test_sem_linguagem_de_recomendacao(self, dados):
        mensagem = montar_mensagem(destinatario="x@y.z", **dados)
        texto = mensagem.assunto + "\n" + mensagem.corpo
        assert varrer_linguagem_recomendacao(texto) == ()
        assert varrer_linguagem_promocional(texto) == ()

    def test_declara_quando_faltou_release(self, dados):
        corpo = montar_mensagem(destinatario="x@y.z", **{**dados, "n_obtido": 2}).corpo
        assert "2" in corpo and "3" in corpo

    def test_declara_quando_o_dashboard_nao_foi_publicado(self, dados):
        corpo = montar_mensagem(
            destinatario="x@y.z", **{**dados, "url_dashboard": None}
        ).corpo
        assert "não publicado" in corpo or "nao publicado" in corpo

    def test_falha_de_auditoria_aparece_no_aviso(self, dados):
        """Aviso que esconde falha é pior que aviso nenhum."""
        corpo = montar_mensagem(destinatario="x@y.z", **{**dados, "falhas": 2}).corpo
        assert "2" in corpo
        assert "falha" in corpo.lower()


class TestEnvio:
    def test_usa_o_transporte_com_os_parametros_da_config(self, cfg, dados):
        transporte = TransporteFalso()
        mensagem = montar_mensagem(destinatario=cfg.email.destinatario, **dados)
        enviar(mensagem, cfg.email, usuario="conta@exemplo", senha="segredo",
               transporte=transporte)

        assert len(transporte.enviadas) == 1
        enviada = transporte.enviadas[0]
        assert enviada["servidor"] == cfg.email.servidor
        assert enviada["porta"] == cfg.email.porta
        assert enviada["usuario"] == "conta@exemplo"
        assert enviada["mensagem"].destinatario == "prof.manoela@ica.ele.puc-rio.br"

    def test_sem_credencial_falha_alto_e_nao_envia(self, cfg, dados):
        transporte = TransporteFalso()
        mensagem = montar_mensagem(destinatario=cfg.email.destinatario, **dados)
        with pytest.raises(CredencialAusente):
            enviar(mensagem, cfg.email, usuario=None, senha=None, transporte=transporte)
        assert transporte.enviadas == []

    def test_falha_do_servidor_vira_erro_explicito(self, cfg, dados):
        transporte = TransporteFalso(erro=OSError("conexão recusada"))
        mensagem = montar_mensagem(destinatario=cfg.email.destinatario, **dados)
        with pytest.raises(EnvioFalhou) as erro:
            enviar(mensagem, cfg.email, usuario="c", senha="s", transporte=transporte)
        assert "conexão recusada" in str(erro.value)

    def test_mensagem_carrega_remetente_e_destinatario(self, cfg, dados):
        mensagem = montar_mensagem(destinatario=cfg.email.destinatario, **dados)
        assert isinstance(mensagem, Mensagem)
        assert mensagem.destinatario == cfg.email.destinatario


class TestConfig:
    def test_destinatario_vem_da_configuracao(self, cfg):
        assert cfg.email.destinatario == "prof.manoela@ica.ele.puc-rio.br"

    def test_credencial_nao_esta_na_configuracao(self, cfg):
        """Segredo em arquivo versionado vaza no primeiro push."""
        assert not hasattr(cfg.email, "senha")
        assert not hasattr(cfg.email, "usuario")
