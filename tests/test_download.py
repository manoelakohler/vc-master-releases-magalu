"""Download e validação dos PDFs.

O SHA-256 é o que permite a alguém verificar, meses depois, que a análise se
refere àquele arquivo exato. PDF digitalizado vira pendência: sem OCR, sem
transcrição manual, sem procurar o número em outro lugar.
"""

import hashlib

import pytest

from magalu_releases.fonte.download import (
    DestinoInvalido,
    baixar_documento,
    calcular_sha256,
    validar_pdf_textual,
)
from magalu_releases.vocabularios import TipoDocumento


class RespostaFalsa:
    def __init__(self, conteudo, content_type="application/pdf"):
        self.status = 200
        self.url_final = "https://exemplo/doc.pdf"
        self.conteudo = conteudo
        self.content_type = content_type


class ClienteFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.pedidos = []

    def obter(self, url, referer=None):
        self.pedidos.append(url)
        return self.resposta


PDF_MINIMO = b"%PDF-1.4\n% conteudo simulado\n%%EOF\n"


class TestHash:
    def test_sha256_bate_com_a_biblioteca_padrao(self):
        assert calcular_sha256(PDF_MINIMO) == hashlib.sha256(PDF_MINIMO).hexdigest()

    def test_sha256_e_deterministico(self):
        assert calcular_sha256(PDF_MINIMO) == calcular_sha256(PDF_MINIMO)

    def test_conteudo_diferente_muda_o_hash(self):
        assert calcular_sha256(PDF_MINIMO) != calcular_sha256(PDF_MINIMO + b"x")


class TestDownload:
    def test_grava_arquivo_e_preenche_rastro(self, tmp_path, documento_valido):
        cliente = ClienteFalso(RespostaFalsa(PDF_MINIMO))
        d = documento_valido(arquivo_local=None, sha256=None, bytes=None, paginas=None)
        baixado = baixar_documento(cliente, d, tmp_path)

        destino = tmp_path / baixado.arquivo_local
        assert destino.is_file()
        assert baixado.bytes == len(PDF_MINIMO)
        assert baixado.sha256 == hashlib.sha256(PDF_MINIMO).hexdigest()
        assert baixado.baixado_em

    def test_usa_a_url_oficial_do_documento(self, tmp_path, documento_valido):
        cliente = ClienteFalso(RespostaFalsa(PDF_MINIMO))
        d = documento_valido()
        baixar_documento(cliente, d, tmp_path)
        assert cliente.pedidos == [d.url_origem]

    def test_conteudo_que_nao_e_pdf_falha_alto(self, tmp_path, documento_valido):
        cliente = ClienteFalso(RespostaFalsa(b"<html>bloqueado</html>", "text/html"))
        with pytest.raises(DestinoInvalido):
            baixar_documento(cliente, documento_valido(), tmp_path)

    def test_destino_inexistente_e_criado(self, tmp_path, documento_valido):
        cliente = ClienteFalso(RespostaFalsa(PDF_MINIMO))
        alvo = tmp_path / "novo" / "lugar"
        baixado = baixar_documento(cliente, documento_valido(), alvo)
        assert (alvo / baixado.arquivo_local).is_file()


class TestTextualidade:
    def test_pdf_com_texto_suficiente_e_textual(self):
        paginas = ["conteúdo textual relevante " * 10 for _ in range(5)]
        resultado = validar_pdf_textual(paginas, minimo_caracteres=50, proporcao_minima=0.5)
        assert resultado.textual is True
        assert resultado.motivo is None

    def test_pdf_sem_camada_de_texto_nao_e_processado(self):
        """Sem OCR: PDF digitalizado vira pendência e a análise segue sem ele."""
        resultado = validar_pdf_textual(["", "", ""], minimo_caracteres=50, proporcao_minima=0.5)
        assert resultado.textual is False
        assert resultado.motivo

    def test_maioria_de_paginas_vazias_reprova(self):
        paginas = ["texto longo o suficiente para passar " * 3, "", "", ""]
        resultado = validar_pdf_textual(paginas, minimo_caracteres=50, proporcao_minima=0.5)
        assert resultado.textual is False

    def test_sem_paginas_reprova(self):
        resultado = validar_pdf_textual([], minimo_caracteres=50, proporcao_minima=0.5)
        assert resultado.textual is False
        assert resultado.motivo
