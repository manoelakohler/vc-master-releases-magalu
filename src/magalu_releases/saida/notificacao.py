"""Aviso de conclusão por e-mail.

Junto com a coleta, é a única parte do projeto que sai para a rede — e por isso
o transporte é injetável, como o cliente HTTP. Assim nenhum teste automatizado
abre socket, e a regra de que rede não entra em teste continua valendo.

Duas decisões que não são de estilo:

- **Credencial vem do ambiente, nunca da configuração.** `settings.toml` é
  versionado e o repositório é público; segredo ali vaza no primeiro push.
- **O aviso não esconde o desfavorável.** Falha de auditoria, release faltando
  e dashboard não publicado aparecem no corpo. Um aviso que só conta a parte
  boa faz o leitor acreditar numa cobertura que a execução não teve.

O corpo é artefato do projeto como qualquer outro: descritivo, sem recomendação
de investimento.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable

from magalu_releases.config import ConfigEmail


class CredencialAusente(Exception):
    """Usuário ou senha do SMTP não estão no ambiente."""


class EnvioFalhou(Exception):
    """O servidor recusou a mensagem ou não pôde ser alcançado."""


@dataclass(frozen=True, slots=True)
class Mensagem:
    destinatario: str
    assunto: str
    corpo: str


def montar_mensagem(
    *,
    destinatario: str,
    run_id: str,
    rotulos,
    n_pedido: int,
    n_obtido: int,
    url_dashboard: str | None,
    verificacoes: int,
    falhas: int,
    pendencias: int,
) -> Mensagem:
    """Monta o aviso a partir do que a execução apurou. Determinístico."""
    rotulos = tuple(rotulos)
    periodos = ", ".join(rotulos)
    intervalo = f"{rotulos[0]} a {rotulos[-1]}" if len(rotulos) > 1 else periodos

    linhas = [
        "A análise de releases de resultados da Magazine Luiza terminou.",
        "",
        f"Períodos analisados: {periodos} ({n_obtido} de {n_pedido} pedidos).",
    ]
    if n_obtido < n_pedido:
        linhas.append(
            f"Atenção: foram pedidos {n_pedido} releases e localizados {n_obtido}."
        )

    linhas.append(
        f"Auditoria: {verificacoes} verificações, {falhas} falha(s). "
        f"Pendências abertas: {pendencias}."
    )
    linhas.append(
        f"Dashboard: {url_dashboard}" if url_dashboard
        else "Dashboard: ainda não publicado."
    )
    linhas.extend([
        "",
        f"Execução: {run_id}",
        "Análise independente, elaborada a partir dos releases públicos divulgados",
        "pela companhia. Conteúdo descritivo e rastreável, limitado ao que os",
        "documentos reportam; não constitui aconselhamento de investimento.",
    ])

    return Mensagem(
        destinatario=destinatario,
        assunto=f"Análise de releases Magalu concluída — {intervalo}",
        corpo="\n".join(linhas),
    )


def _transporte_smtp(
    mensagem: Mensagem, *, servidor: str, porta: int, usar_tls: bool,
    usuario: str, senha: str,
) -> None:
    """A fronteira real. Substituída por um duplo nos testes."""
    email = EmailMessage()
    email["From"] = usuario
    email["To"] = mensagem.destinatario
    email["Subject"] = mensagem.assunto
    email.set_content(mensagem.corpo)

    with smtplib.SMTP(servidor, porta, timeout=30) as conexao:
        if usar_tls:
            conexao.starttls()
        conexao.login(usuario, senha)
        conexao.send_message(email)


def enviar(
    mensagem: Mensagem,
    cfg: ConfigEmail,
    *,
    usuario: str | None,
    senha: str | None,
    transporte: Callable[..., None] = _transporte_smtp,
) -> None:
    """Envia o aviso. Falha alto: nunca devolve sucesso sem ter enviado."""
    if not (usuario or "").strip() or not (senha or "").strip():
        raise CredencialAusente(
            "defina MAGALU_SMTP_USUARIO e MAGALU_SMTP_SENHA no ambiente; "
            "a credencial não vem do arquivo de configuração"
        )

    try:
        transporte(
            mensagem,
            servidor=cfg.servidor,
            porta=cfg.porta,
            usar_tls=cfg.usar_tls,
            usuario=usuario,
            senha=senha,
        )
    except Exception as erro:  # rede, autenticação, recusa do servidor
        raise EnvioFalhou(f"não foi possível enviar o aviso: {erro}") from erro
