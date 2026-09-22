"""Descoberta dos documentos publicados na Central de Resultados.

A leitura percorre as âncoras na ordem do documento e associa cada link ao
último período visto. Isso é deliberado: seletores CSS fixos quebram no primeiro
redesenho do site de RI, enquanto a sequência "cabeçalho de período, depois seus
documentos" é a estrutura lógica da página e sobrevive melhor.

O período do próprio rótulo do link tem prioridade sobre o do cabeçalho — quando
o site escreve "Release de Resultados 3T25", essa é a informação mais específica
disponível.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from magalu_releases.fonte.classificacao import classificar_documento
from magalu_releases.periodos import PeriodoFiscal, PeriodoIndeterminado, interpretar_periodo
from magalu_releases.vocabularios import TipoDocumento

# Reconhece o período dentro de um texto qualquer (cabeçalho, rótulo de link).
_PERIODO_NO_TEXTO = re.compile(r"\b([1-4]\s?[TQ]\s?\d{2,4}|\d{1,2}\s?M\s?\d{2,4})\b", re.IGNORECASE)

_ESQUEMAS_IGNORADOS = ("javascript:", "mailto:", "tel:", "#")

_POSTBACK = re.compile(r"__doPostBack", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DocumentoDescoberto:
    documento_id: str
    titulo: str
    url_origem: str
    tipo: TipoDocumento
    periodo: PeriodoFiscal | None
    periodo_texto: str | None


def tem_paginacao(html: str) -> bool:
    """A Central pagina por postback. Para N grande, a primeira página não basta."""
    return bool(_POSTBACK.search(html))


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
    """Lista os documentos da página, com tipo e período quando determináveis."""
    from bs4 import BeautifulSoup

    sopa = BeautifulSoup(html, "lxml")
    encontrados: list[DocumentoDescoberto] = []
    vistos: set[str] = set()
    periodo_corrente: PeriodoFiscal | None = None
    texto_periodo_corrente: str | None = None

    # A ordem do documento é o que liga cabeçalho de período aos seus links.
    for elemento in sopa.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "a"]):
        texto = elemento.get_text(" ", strip=True)

        if elemento.name != "a":
            if candidato := _periodo_de(texto):
                periodo_corrente = candidato
                texto_periodo_corrente = texto
            continue

        href = (elemento.get("href") or "").strip()
        if not href or href.lower().startswith(_ESQUEMAS_IGNORADOS):
            continue

        url = urljoin(base_url, href)
        if url in vistos:
            continue
        vistos.add(url)

        # O rótulo do próprio link é mais específico que o cabeçalho do grupo.
        periodo = _periodo_de(texto) or _periodo_de(href) or periodo_corrente
        periodo_texto = (
            texto if _periodo_de(texto) else (texto_periodo_corrente if periodo else None)
        )

        encontrados.append(
            DocumentoDescoberto(
                documento_id=_identificador(url),
                titulo=texto,
                url_origem=url,
                tipo=classificar_documento(texto, url=url),
                periodo=periodo,
                periodo_texto=periodo_texto,
            )
        )

    return encontrados
