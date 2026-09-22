"""Classificação dos documentos da Central de Resultados.

O critério de inclusão é **positivo**: um documento só é release se ele se
identifica como tal. Documento cuja natureza não dá para determinar vira
`NAO_CLASSIFICADO` e depois pendência — nunca é promovido a release por
eliminação, porque a estrutura numérica de um ITR é diferente e a contaminação
resultante é invisível na planilha.

A ordem de avaliação importa: "Apresentação de Resultados" contém "Resultados",
então as exclusões são testadas antes do padrão de release.
"""

from __future__ import annotations

import re
import unicodedata

from magalu_releases.vocabularios import TipoDocumento


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento: os rótulos variam entre releases."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


# Avaliadas em ordem. A primeira que casar decide.
_EXCLUSOES: tuple[tuple[re.Pattern[str], TipoDocumento], ...] = (
    (re.compile(r"\bitr\b|\bdfp\b|informacoes trimestrais|demonstracoes financeiras padronizadas"),
     TipoDocumento.ITR_DFP),
    (re.compile(r"demonstracoes financeiras|demonstracoes contabeis"),
     TipoDocumento.DEMONSTRACOES_FINANCEIRAS),
    (re.compile(r"formulario de referencia"), TipoDocumento.FORMULARIO_REFERENCIA),
    (re.compile(r"transcricao"), TipoDocumento.TRANSCRICAO),
    (re.compile(r"audio|teleconferencia|webcast|conference call"),
     TipoDocumento.AUDIO_TELECONFERENCIA),
    (re.compile(r"apresentacao|presentation|\bslides?\b"), TipoDocumento.APRESENTACAO),
    (re.compile(r"planilha|spreadsheet|\bxlsx?\b"), TipoDocumento.PLANILHA),
    (re.compile(r"fato relevante"), TipoDocumento.FATO_RELEVANTE),
    (re.compile(r"comunicado|aviso aos acionistas|\bata\b|assembleia"), TipoDocumento.COMUNICADO),
    (re.compile(r"sustentabilidade|\besg\b|relato integrado"), TipoDocumento.SUSTENTABILIDADE),
)

_RELEASE = re.compile(r"release de resultados?|divulgacao de resultados?|earnings release|\brelease\b")


def classificar_documento(titulo: str | None, url: str | None = None) -> TipoDocumento:
    """Determina o tipo do documento a partir do rótulo e, subsidiariamente, da URL.

    O título tem prioridade: quando ele diz "Apresentação", uma URL que contenha
    "release" não muda o que o documento é.
    """
    rotulo = _normalizar(titulo or "")

    if rotulo:
        for padrao, tipo in _EXCLUSOES:
            if padrao.search(rotulo):
                return tipo
        if _RELEASE.search(rotulo):
            return TipoDocumento.RELEASE_RESULTADOS

    if url:
        caminho = _normalizar(url)
        for padrao, tipo in _EXCLUSOES:
            if padrao.search(caminho):
                return tipo
        if _RELEASE.search(caminho):
            return TipoDocumento.RELEASE_RESULTADOS

    return TipoDocumento.NAO_CLASSIFICADO
