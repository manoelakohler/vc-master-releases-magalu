"""Gerador de PDFs textuais mínimos para teste.

Nenhuma dependência instalada escreve PDF, e acrescentar uma só para gerar
fixture seria peso morto em produção. Estes bytes são um PDF 1.4 válido,
montado à mão com a tabela xref correta.
"""

from __future__ import annotations


def _escapar(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def construir_pdf(paginas: list[list[str]]) -> bytes:
    """Monta um PDF com uma página por item; cada item é uma lista de linhas."""
    objetos: list[bytes] = []

    n_paginas = len(paginas)
    ids_paginas = [3 + i * 2 for i in range(n_paginas)]
    id_fonte = 3 + n_paginas * 2

    objetos.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = b" ".join(b"%d 0 R" % i for i in ids_paginas)
    objetos.append(b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % n_paginas)

    for indice, linhas in enumerate(paginas):
        id_pagina = ids_paginas[indice]
        id_conteudo = id_pagina + 1
        comandos = ["BT", "/F1 11 Tf", "1 0 0 1 56 760 Tm", "14 TL"]
        for linha in linhas:
            comandos.append(f"({_escapar(linha)}) Tj")
            comandos.append("T*")
        comandos.append("ET")
        fluxo = "\n".join(comandos).encode("latin-1", "replace")

        objetos.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (id_fonte, id_conteudo)
        )
        objetos.append(
            b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"\nendstream"
        )

    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos: list[int] = []
    for numero, corpo in enumerate(objetos, start=1):
        deslocamentos.append(len(saida))
        saida += b"%d 0 obj\n" % numero + corpo + b"\nendobj\n"

    inicio_xref = len(saida)
    total = len(objetos) + 1
    saida += b"xref\n0 %d\n" % total
    saida += b"0000000000 65535 f \n"
    for deslocamento in deslocamentos:
        saida += b"%010d 00000 n \n" % deslocamento
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        total,
        inicio_xref,
    )
    return bytes(saida)


PAGINA_TABELA = [
    "MAGAZINE LUIZA S.A.",
    "Release de Resultados - 2T25",
    "",
    "(R$ milhoes)            2T25        2T24     Var.",
    "Receita Liquida       9.856,4     9.112,0    8,2%",
    "Lucro Bruto           2.741,2     2.510,8    9,2%",
    "Margem Bruta            27,8%       27,6%   0,2 p.p.",
    "EBITDA Ajustado         988,7       901,4    9,7%",
    "Prejuizo Liquido        135,0        88,2      n.a.",
]

PAGINA_NARRATIVA = [
    "Comentario da Administracao",
    "",
    "A receita liquida do trimestre alcancou quase R$ 10 bilhoes,",
    "com crescimento em relacao ao mesmo periodo do ano anterior.",
]
