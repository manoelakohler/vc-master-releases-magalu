"""PDF para texto, preservando documento e página.

A unidade de extração é (documento, página) porque é isso que torna a evidência
conferível: um humano abre a página indicada e vê o número em segundos.

Este módulo também sinaliza quando a estrutura de uma tabela se perdeu na
extração. Não tenta consertar o alinhamento — um número na linha errada é
invisível na planilha, enquanto um campo vazio com pendência é visível e
alguém o investiga.
"""

from __future__ import annotations

import re
from pathlib import Path

from magalu_releases.models import PaginaTexto

_ASSINATURA_PDF = b"%PDF-"

# Token numérico brasileiro: 9.856,4 | 27,8% | 1.245 | 0,2
_TOKEN_NUMERICO = re.compile(r"\d[\d.]*(?:,\d+)?%?")

# Dois decimais no mesmo token: "9.856,49.112,0" é o sintoma clássico de
# colunas fundidas pela extração.
_DECIMAIS_COLADOS = re.compile(r",\d+[.\d]*,\d")

_MINIMO_TOKENS_NA_LINHA = 3
_MINIMO_LINHAS_DENSAS = 2


class PdfIlegivel(Exception):
    """O arquivo não pôde ser aberto ou não é um PDF."""


def detectar_estrutura_perdida(texto: str, *, tabelas_detectadas: int) -> tuple[bool, str | None]:
    """Decide se a página tem números em grade cuja estrutura não foi recuperada.

    Dois sinais independentes:

    1. Decimais colados num mesmo token — duas colunas viraram uma.
    2. Várias linhas densas em números sem que nenhuma tabela tenha sido
       reconhecida — há grade na página, mas não foi possível reconstruí-la.

    Página narrativa e página vazia não disparam: o objetivo é marcar perda de
    estrutura, não a mera presença de tabelas.
    """
    if not texto or not texto.strip():
        return False, None

    if _DECIMAIS_COLADOS.search(texto):
        return True, "valores decimais concatenados: colunas fundidas na extração"

    if tabelas_detectadas > 0:
        return False, None

    densas = sum(
        1
        for linha in texto.splitlines()
        if len(_TOKEN_NUMERICO.findall(linha)) >= _MINIMO_TOKENS_NA_LINHA
    )
    if densas >= _MINIMO_LINHAS_DENSAS:
        return True, (
            f"{densas} linhas com 3+ números e nenhuma tabela reconhecida: "
            "alinhamento de colunas não confirmado"
        )

    return False, None


def extrair_paginas(caminho_pdf: Path | str, *, documento_id: str) -> list[PaginaTexto]:
    """Extrai o texto de cada página. Falha alto se o arquivo não for legível."""
    caminho = Path(caminho_pdf)
    if not caminho.is_file():
        raise PdfIlegivel(f"arquivo não encontrado: {caminho}")

    with caminho.open("rb") as arquivo:
        if not arquivo.read(5).startswith(_ASSINATURA_PDF):
            raise PdfIlegivel(f"{caminho} não começa com assinatura de PDF")

    import pdfplumber

    paginas: list[PaginaTexto] = []
    try:
        with pdfplumber.open(caminho) as pdf:
            for numero, pagina in enumerate(pdf.pages, start=1):
                texto = pagina.extract_text() or ""
                try:
                    tabelas = len(pagina.extract_tables() or [])
                except Exception:
                    tabelas = 0
                perdida, motivo = detectar_estrutura_perdida(
                    texto, tabelas_detectadas=tabelas
                )
                paginas.append(
                    PaginaTexto(
                        documento_id=documento_id,
                        pagina=numero,
                        texto=texto,
                        caracteres=len(texto),
                        tabela_suspeita=perdida,
                        observacao=motivo,
                    )
                )
    except PdfIlegivel:
        raise
    except Exception as exc:
        raise PdfIlegivel(f"falha ao ler {caminho}: {exc}") from exc

    return paginas
