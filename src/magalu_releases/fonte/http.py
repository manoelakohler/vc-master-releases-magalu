"""Cliente HTTP — a única fronteira de rede do projeto.

Tudo que toca a internet passa por aqui, o que permite que nenhum teste
automatizado dependa de rede (exigência do CLAUDE.md).

O spike da etapa 1 determinou o comportamento necessário: o edge (WAF Azion) do
site de RI recusa clientes sem o conjunto completo de cabeçalhos de navegador e
aplica rate limiting por IP. Rajadas entram em janela de bloqueio. Por isso o
cliente espaça requisições e faz backoff exponencial em vez de insistir.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol

from magalu_releases.config import ConfigHttp


class FalhaHttp(Exception):
    """A requisição não pôde ser concluída. Falha alto: nunca devolve conteúdo parcial."""


@dataclass(frozen=True, slots=True)
class Resposta:
    status: int
    url_final: str
    conteudo: bytes
    content_type: str


class _Sessao(Protocol):
    headers: dict
    def get(self, url: str, **kwargs): ...


class ClienteHttp:
    def __init__(
        self,
        cfg: ConfigHttp,
        *,
        sessao: _Sessao | None = None,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = cfg
        self.dormir = dormir
        self.agora = agora
        self._ultimo_acesso: float | None = None
        # Registrado para auditoria: quantas vezes o edge nos barrou e por quanto tempo
        # esperamos. Rate limiting é fato da coleta, não ruído de log.
        self.esperas_backoff: list[float] = []

        if sessao is None:
            import requests

            sessao = requests.Session()
        self.sessao = sessao
        self.sessao.headers.update(dict(cfg.cabecalhos))

    def _aguardar_intervalo(self) -> None:
        """Espaça as requisições. Sem isso, o edge bloqueia o IP por uma janela."""
        if self._ultimo_acesso is None:
            self.dormir(0)
            return
        decorrido = self.agora() - self._ultimo_acesso
        restante = self.cfg.intervalo_entre_requisicoes - decorrido
        self.dormir(max(restante, 0.0))

    def obter(self, url: str, *, referer: str | None = None) -> Resposta:
        cabecalhos: dict[str, str] = {}
        if referer:
            cabecalhos["Referer"] = referer
            cabecalhos["Sec-Fetch-Site"] = "same-origin"

        ultimo_status: int | None = None
        for tentativa in range(1, self.cfg.tentativas_maximas + 1):
            self._aguardar_intervalo()
            bruta = self.sessao.get(
                url, headers=cabecalhos, timeout=self.cfg.timeout_segundos
            )
            self._ultimo_acesso = self.agora()
            status = bruta.status_code
            ultimo_status = status

            if 200 <= status < 300:
                return Resposta(
                    status=status,
                    url_final=getattr(bruta, "url", url),
                    conteudo=bruta.content,
                    content_type=bruta.headers.get("Content-Type", ""),
                )

            if status not in self.cfg.status_para_retentar:
                raise FalhaHttp(f"HTTP {status} em {url} (não é status para retentar)")

            if tentativa < self.cfg.tentativas_maximas:
                espera = self.cfg.backoff_base_segundos * (
                    self.cfg.backoff_fator ** (tentativa - 1)
                )
                self.esperas_backoff.append(espera)
                self.dormir(espera)

        raise FalhaHttp(
            f"HTTP {ultimo_status} em {url} após {self.cfg.tentativas_maximas} tentativas"
        )
