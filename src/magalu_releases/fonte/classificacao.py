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


# O controle ASP.NET da Central nomeia o tipo no próprio id da âncora:
# `..._rptResultados_linkArq_Release1T_0`. É a única declaração de tipo no
# markup — o href é um token opaco e a âncora diz apenas "PDF".
_IDENTIFICADOR = re.compile(r"linkArq_([A-Za-z]+?)([1-4])T_\d+$", re.IGNORECASE)

_TIPOS_POR_IDENTIFICADOR = {
    "release": TipoDocumento.RELEASE_RESULTADOS,
    "itr": TipoDocumento.ITR_DFP,
    "apresentacao": TipoDocumento.APRESENTACAO,
    "audio": TipoDocumento.AUDIO_TELECONFERENCIA,
    "transcricao": TipoDocumento.TRANSCRICAO,
}

# Nome com que o servidor devolve o release: `MGLU_ER_1T26_POR.pdf` (ER de
# earnings release) ou o nome por extenso.
_NOME_DE_RELEASE = re.compile(
    r"(?:^|[_\s-])er[_\s-]|release de resultados?|divulgacao de resultados?|earnings release",
    re.IGNORECASE,
)
# `\b` não serve aqui: em `MGLU_ER_1T26_POR` o underscore é caractere de
# palavra, então não há fronteira antes do dígito.
_PERIODO_NO_NOME = re.compile(r"(?<![0-9])([1-4])\s?T\s?(\d{2,4})(?![0-9])", re.IGNORECASE)


def classificar_por_identificador(identificador: str | None) -> TipoDocumento:
    """Tipo declarado pelo id do controle, na listagem da Central.

    Identificador que não casa com nenhum tipo conhecido vira
    `NAO_CLASSIFICADO` — nunca release por eliminação.
    """
    achado = _IDENTIFICADOR.search(identificador or "")
    if not achado:
        return TipoDocumento.NAO_CLASSIFICADO
    return _TIPOS_POR_IDENTIFICADOR.get(
        _normalizar(achado.group(1)), TipoDocumento.NAO_CLASSIFICADO
    )


def trimestre_do_identificador(identificador: str | None) -> int | None:
    """Trimestre embutido no id, para conferir contra o rótulo da linha."""
    achado = _IDENTIFICADOR.search(identificador or "")
    return int(achado.group(2)) if achado else None


def confirmar_release(nome_servidor: str | None, periodo_rotulo: str) -> tuple[bool, str | None]:
    """O arquivo baixado é mesmo o release daquele período?

    O `Content-Disposition` do próprio download já traz a resposta, sem custo de
    rede. Divergência aqui não é detalhe de nomenclatura: significa que o token
    da Central aponta para outro documento, e seguir em frente colocaria números
    de outro período — ou de outro tipo de demonstração — na planilha.
    """
    if not (nome_servidor or "").strip():
        return False, "o servidor não nomeou o arquivo baixado (sem Content-Disposition)"

    nome = nome_servidor.strip()
    if not _NOME_DE_RELEASE.search(_normalizar(nome)):
        return False, (
            f"o servidor nomeou o arquivo {nome!r}, que não se identifica como "
            "release de resultados"
        )

    achado = _PERIODO_NO_NOME.search(nome)
    if achado:
        ano = achado.group(2)
        no_nome = f"{achado.group(1)}T{ano[-2:]}"
        esperado = periodo_rotulo.replace(" ", "").upper()
        if no_nome.upper() != esperado and no_nome.upper() not in esperado:
            return False, (
                f"o servidor nomeou o arquivo como {no_nome}, mas a Central o "
                f"listou em {periodo_rotulo}"
            )

    return True, None


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
