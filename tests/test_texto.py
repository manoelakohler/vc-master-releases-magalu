"""Extração de texto preservando documento e página.

A página é o que torna a evidência verificável por um humano em segundos. Sem
ela, "está no release" é inútil.

Quando a extração colapsa uma tabela, não se adivinha o alinhamento: um número
na linha errada é indetectável depois, ao contrário de um campo vazio.
"""

import pytest

from fixtures.pdf_sintetico import PAGINA_NARRATIVA, PAGINA_TABELA, construir_pdf
from magalu_releases.extracao.texto import (
    PdfIlegivel,
    detectar_estrutura_perdida,
    extrair_paginas,
)


@pytest.fixture
def pdf_duas_paginas(tmp_path):
    caminho = tmp_path / "release.pdf"
    caminho.write_bytes(construir_pdf([PAGINA_TABELA, PAGINA_NARRATIVA]))
    return caminho


class TestExtracao:
    def test_uma_entrada_por_pagina(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert len(paginas) == 2

    def test_numeracao_comeca_em_um(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert [p.pagina for p in paginas] == [1, 2]

    def test_documento_fica_amarrado_a_cada_pagina(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert all(p.documento_id == "doc-2t25" for p in paginas)

    def test_texto_da_pagina_certa(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert "Receita Liquida" in paginas[0].texto
        assert "Comentario da Administracao" in paginas[1].texto
        assert "Comentario" not in paginas[0].texto

    def test_valores_chegam_intactos(self, pdf_duas_paginas):
        """O texto extraído precisa conter o valor tal como impresso."""
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert "9.856,4" in paginas[0].texto
        assert "0,2 p.p." in paginas[0].texto

    def test_contagem_de_caracteres(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert all(p.caracteres == len(p.texto) for p in paginas)


class TestFalhas:
    def test_arquivo_inexistente_falha_alto(self, tmp_path):
        with pytest.raises(PdfIlegivel):
            extrair_paginas(tmp_path / "nao-existe.pdf", documento_id="x")

    def test_arquivo_que_nao_e_pdf_falha_alto(self, tmp_path):
        ruim = tmp_path / "ruim.pdf"
        ruim.write_bytes(b"<html>bloqueado</html>")
        with pytest.raises(PdfIlegivel):
            extrair_paginas(ruim, documento_id="x")


class TestEstruturaPerdida:
    def test_numeros_colados_indicam_perda(self):
        perdida, motivo = detectar_estrutura_perdida(
            "Receita Liquida 9.856,49.112,0 8,2%", tabelas_detectadas=0
        )
        assert perdida is True
        assert motivo

    def test_linhas_numericas_sem_tabela_reconhecida(self):
        texto = (
            "Receita Liquida 9.856,4 9.112,0 8,2%\n"
            "Lucro Bruto 2.741,2 2.510,8 9,2%\n"
            "EBITDA 988,7 901,4 9,7%\n"
        )
        perdida, motivo = detectar_estrutura_perdida(texto, tabelas_detectadas=0)
        assert perdida is True

    def test_tabela_reconhecida_nao_e_suspeita(self):
        texto = "Receita Liquida 9.856,4 9.112,0 8,2%\nLucro Bruto 2.741,2 2.510,8 9,2%\n"
        perdida, _ = detectar_estrutura_perdida(texto, tabelas_detectadas=2)
        assert perdida is False

    def test_texto_narrativo_nao_e_suspeito(self):
        texto = (
            "A receita liquida do trimestre alcancou quase R$ 10 bilhoes, "
            "com crescimento em relacao ao mesmo periodo do ano anterior."
        )
        perdida, _ = detectar_estrutura_perdida(texto, tabelas_detectadas=0)
        assert perdida is False

    def test_pagina_vazia_nao_e_suspeita(self):
        perdida, _ = detectar_estrutura_perdida("", tabelas_detectadas=0)
        assert perdida is False


class TestMarcacaoNaPagina:
    def test_pagina_de_tabela_recebe_marca(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert paginas[0].tabela_suspeita is True
        assert paginas[0].observacao

    def test_pagina_narrativa_nao_recebe_marca(self, pdf_duas_paginas):
        paginas = extrair_paginas(pdf_duas_paginas, documento_id="doc-2t25")
        assert paginas[1].tabela_suspeita is False
