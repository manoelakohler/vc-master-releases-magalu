"""Download dos PDFs e validação de textualidade.

O hash é o que sustenta a auditoria meses depois: sem ele, "o release do 2T25"
é uma referência que ninguém consegue reproduzir.

PDF sem camada de texto não é processado e não é resolvido de outra forma — sem
OCR, sem transcrição manual, sem buscar o número em outro lugar. Vira pendência.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from magalu_releases.models import Documento

_ASSINATURA_PDF = b"%PDF-"
_NAO_ALFANUM = re.compile(r"[^A-Za-z0-9._-]+")


class DestinoInvalido(Exception):
    """O conteúdo recebido não é um PDF utilizável."""


@dataclass(frozen=True, slots=True)
class ResultadoTextualidade:
    textual: bool
    paginas_com_texto: int
    paginas_totais: int
    motivo: str | None = None


def calcular_sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _nome_arquivo(documento: Documento) -> str:
    seguro = _NAO_ALFANUM.sub("-", documento.documento_id).strip("-") or "documento"
    return f"{seguro}.pdf"


def baixar_documento(cliente, documento: Documento, diretorio: Path | str) -> Documento:
    """Baixa o PDF da URL oficial e devolve o documento com o rastro preenchido.

    Falha alto quando o conteúdo não é PDF: um HTML de bloqueio gravado com
    extensão .pdf viraria "documento ilegível" lá na frente, escondendo a causa
    real, que é a coleta.
    """
    destino = Path(diretorio)
    destino.mkdir(parents=True, exist_ok=True)

    resposta = cliente.obter(documento.url_origem)
    conteudo = resposta.conteudo

    if not conteudo.startswith(_ASSINATURA_PDF):
        inicio = conteudo[:40]
        raise DestinoInvalido(
            f"conteúdo de {documento.url_origem} não é PDF "
            f"(content-type={resposta.content_type!r}, início={inicio!r})"
        )

    # O nome local vem do documento_id, nunca do servidor: nome de arquivo
    # vindo de fora é caminho controlado por terceiro.
    nome = _nome_arquivo(documento)
    (destino / nome).write_bytes(conteudo)

    return replace(
        documento,
        arquivo_local=nome,
        nome_servidor=getattr(resposta, "nome_arquivo", None),
        bytes=len(conteudo),
        sha256=calcular_sha256(conteudo),
        baixado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def validar_pdf_textual(
    textos_por_pagina, *, minimo_caracteres: int, proporcao_minima: float
) -> ResultadoTextualidade:
    """Decide se o PDF tem camada de texto utilizável.

    O critério é por proporção de páginas, e não pelo total de caracteres: um
    release com capa e contracapa vazias continua textual, mas um escaneado com
    uma única página de texto não passa a ser.
    """
    paginas = list(textos_por_pagina)
    total = len(paginas)
    if total == 0:
        return ResultadoTextualidade(False, 0, 0, "PDF sem páginas legíveis")

    com_texto = sum(1 for t in paginas if len((t or "").strip()) >= minimo_caracteres)
    proporcao = com_texto / total

    if proporcao < proporcao_minima:
        return ResultadoTextualidade(
            False,
            com_texto,
            total,
            f"apenas {com_texto}/{total} páginas com texto "
            f"(mínimo {proporcao_minima:.0%}); sem OCR, o documento não é processado",
        )

    return ResultadoTextualidade(True, com_texto, total, None)
