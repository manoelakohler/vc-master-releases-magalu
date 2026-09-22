"""Descoberta dos documentos publicados na Central de Resultados.

A Central é uma tabela: uma linha por trimestre, o rótulo do período na
primeira célula e, nas seguintes, os arquivos daquele período. Os links são
**opacos** — `Download.aspx?Arquivo=<token>` — e a âncora diz apenas "PDF".

Isso tem uma consequência que decide o desenho deste módulo: o único lugar do
markup que declara **o que** cada arquivo é fica no `id` do controle ASP.NET
(`..._rptResultados_linkArq_Release1T_0`). Sem ele restaria a posição do link na
linha, e deduzir tipo de documento por posição é adivinhar — justamente o que
contamina a comparação de forma invisível quando um ITR entra como release.

A URL da própria Central carrega um token de canal e é descoberta a partir da
home a cada execução. Congelá-la em configuração é o que fez a coleta responder
HTTP 500 quando o site mudou.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from magalu_releases.fonte.classificacao import (
    classificar_por_identificador,
    trimestre_do_identificador,
)
from magalu_releases.periodos import PeriodoFiscal, PeriodoIndeterminado, interpretar_periodo
from magalu_releases.vocabularios import TipoDocumento

_PERIODO_NO_TEXTO = re.compile(r"\b([1-4]\s?[TQ]\s?\d{2,4}|\d{1,2}\s?M\s?\d{2,4})\b", re.IGNORECASE)

_POSTBACK = re.compile(r"__doPostBack", re.IGNORECASE)

_ARQUIVO = re.compile(r"Download\.aspx\?Arquivo=", re.IGNORECASE)

# Marca do tipo dentro do id do controle: `linkArq_Release1T_0` -> "Release".
_MARCA_NO_ID = re.compile(r"linkArq_([A-Za-z]+?)[1-4]T_\d+$", re.IGNORECASE)

# O link para a Central mora na home e carrega o token do canal.
_LINK_CENTRAL = re.compile(r"listresultados", re.IGNORECASE)


class CentralNaoEncontrada(Exception):
    """A home não expõe o link da Central de Resultados."""


@dataclass(frozen=True, slots=True)
class DocumentoDescoberto:
    documento_id: str
    titulo: str
    url_origem: str
    tipo: TipoDocumento
    periodo: PeriodoFiscal | None
    periodo_texto: str | None
    trimestre_declarado: int | None = None


def tem_paginacao(html: str) -> bool:
    """A Central pagina por postback. Hoje a primeira página traz a série inteira."""
    return bool(_POSTBACK.search(html))


def encontrar_url_central(html: str, *, base_url: str) -> str:
    """Extrai da home a URL da Central, com o token de canal que o site exige.

    Falha alto quando o link não está lá: sem a Central não há fonte oficial, e
    montar uma URL por conta própria seria trocar a fonte por um palpite.
    """
    from bs4 import BeautifulSoup

    sopa = BeautifulSoup(html, "lxml")
    candidatos = [
        urljoin(base_url, (a.get("href") or "").strip())
        for a in sopa.find_all("a")
        if _LINK_CENTRAL.search(a.get("href") or "")
    ]
    if not candidatos:
        raise CentralNaoEncontrada(
            "a home não traz link para a Central de Resultados: "
            "a estrutura do site pode ter mudado"
        )

    # O link completo (com nome da seção) é mais específico que o .aspx cru.
    com_token = [u for u in candidatos if "?=" in u or "idcanal=" in u.lower()]
    preferidos = [u for u in (com_token or candidatos) if "central-de-resultados" in u.lower()]
    return (preferidos or com_token or candidatos)[0]


def _periodo_de(texto: str | None) -> PeriodoFiscal | None:
    if not texto:
        return None
    achado = _PERIODO_NO_TEXTO.search(texto)
    if not achado:
        return None
    try:
        return interpretar_periodo(achado.group(1).strip())
    except PeriodoIndeterminado:
        return None


def _identificador(url: str) -> str:
    """Estável entre execuções: derivado da URL, que é o que identifica o documento."""
    return "doc-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def descobrir_documentos(html: str, *, base_url: str) -> list[DocumentoDescoberto]:
    """Lista os arquivos da Central, com tipo e período lidos do markup."""
    from bs4 import BeautifulSoup

    sopa = BeautifulSoup(html, "lxml")
    encontrados: list[DocumentoDescoberto] = []
    vistos: set[str] = set()

    for linha in sopa.find_all("tr"):
        ancoras = [a for a in linha.find_all("a") if _ARQUIVO.search(a.get("href") or "")]
        if not ancoras:
            continue

        celulas = linha.find_all("td")
        rotulo = celulas[0].get_text(" ", strip=True) if celulas else ""
        periodo = _periodo_de(rotulo)

        for ancora in ancoras:
            url = urljoin(base_url, (ancora.get("href") or "").strip())
            if url in vistos:
                continue
            vistos.add(url)

            identificador = ancora.get("id") or ""
            tipo = classificar_por_identificador(identificador)
            achado = _MARCA_NO_ID.search(identificador)
            marca = achado.group(1) if achado else ""

            encontrados.append(
                DocumentoDescoberto(
                    documento_id=_identificador(url),
                    # O título amarra o que o markup afirma: período da célula e
                    # tipo do id. Depois do download ele é substituído pelo nome
                    # que o próprio servidor deu ao arquivo.
                    titulo=f"{rotulo} · {marca}".strip(" ·") or "documento sem rótulo",
                    url_origem=url,
                    tipo=tipo,
                    periodo=periodo,
                    periodo_texto=rotulo or None,
                    trimestre_declarado=trimestre_do_identificador(identificador),
                )
            )

    return encontrados
