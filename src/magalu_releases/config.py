"""Ponto único de configuração.

Todo valor que poderia ser "constante espalhada pelo código" — URL da fonte,
cabeçalhos HTTP, limiares de PDF, N padrão — entra aqui, vindo de
`config/settings.toml`. As estruturas são congeladas porque configuração mutável
em tempo de execução é o mesmo problema que a configuração centralizada resolve.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_PADRAO = RAIZ_PROJETO / "config" / "settings.toml"


@dataclass(frozen=True, slots=True)
class ConfigExecucao:
    n_padrao: int
    diretorio_execucoes: str


@dataclass(frozen=True, slots=True)
class ConfigFonte:
    nome: str
    base_url: str
    url_central: str
    dominio_oficial: str


@dataclass(frozen=True, slots=True)
class ConfigHttp:
    timeout_segundos: float
    intervalo_entre_requisicoes: float
    tentativas_maximas: int
    backoff_base_segundos: float
    backoff_fator: float
    status_para_retentar: tuple[int, ...]
    cabecalhos: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ConfigPdf:
    minimo_caracteres_por_pagina: int
    minimo_paginas_textuais_proporcao: float


@dataclass(frozen=True, slots=True)
class Config:
    execucao: ConfigExecucao
    fonte: ConfigFonte
    http: ConfigHttp
    pdf: ConfigPdf
    origem: Path


class ConfigInvalida(Exception):
    """A configuração não pôde ser lida ou está incompleta."""


def carregar_config(caminho: Path | str | None = None) -> Config:
    """Lê e valida o arquivo de configuração.

    Falha alto: configuração incompleta é erro explícito, nunca um padrão
    silencioso — um default inventado aqui reapareceria como número errado na
    planilha, sem rastro.
    """
    origem = Path(caminho) if caminho is not None else CAMINHO_PADRAO
    if not origem.is_file():
        raise ConfigInvalida(f"Arquivo de configuração não encontrado: {origem}")

    try:
        dados = tomllib.loads(origem.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigInvalida(f"TOML inválido em {origem}: {exc}") from exc

    try:
        execucao = ConfigExecucao(
            n_padrao=int(dados["execucao"]["n_padrao"]),
            diretorio_execucoes=str(dados["execucao"]["diretorio_execucoes"]),
        )
        fonte = ConfigFonte(
            nome=str(dados["fonte"]["nome"]),
            base_url=str(dados["fonte"]["base_url"]),
            url_central=str(dados["fonte"]["url_central"]),
            dominio_oficial=str(dados["fonte"]["dominio_oficial"]),
        )
        bloco_http = dados["http"]
        http = ConfigHttp(
            timeout_segundos=float(bloco_http["timeout_segundos"]),
            intervalo_entre_requisicoes=float(bloco_http["intervalo_entre_requisicoes"]),
            tentativas_maximas=int(bloco_http["tentativas_maximas"]),
            backoff_base_segundos=float(bloco_http["backoff_base_segundos"]),
            backoff_fator=float(bloco_http["backoff_fator"]),
            status_para_retentar=tuple(int(s) for s in bloco_http["status_para_retentar"]),
            cabecalhos=MappingProxyType(dict(bloco_http["cabecalhos"])),
        )
        pdf = ConfigPdf(
            minimo_caracteres_por_pagina=int(dados["pdf"]["minimo_caracteres_por_pagina"]),
            minimo_paginas_textuais_proporcao=float(
                dados["pdf"]["minimo_paginas_textuais_proporcao"]
            ),
        )
    except KeyError as exc:
        raise ConfigInvalida(f"Chave ausente na configuração {origem}: {exc}") from exc

    if execucao.n_padrao < 1:
        raise ConfigInvalida("execucao.n_padrao precisa ser >= 1")

    return Config(execucao=execucao, fonte=fonte, http=http, pdf=pdf, origem=origem)
