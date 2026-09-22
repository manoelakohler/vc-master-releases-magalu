"""Dossiê da fase semântica e interface de execução.

O dossiê é o pacote que a análise lê. Ele carrega o texto página a página e o
contrato que a saída precisa cumprir — mas não repete o procedimento, que vive
na skill.

A CLI tem uma única entrada de usuário: N.
"""

import json

import pytest

from fixtures.pdf_sintetico import PAGINA_NARRATIVA, PAGINA_TABELA, construir_pdf
from magalu_releases.cli import construir_parser, main
from magalu_releases.extracao.dossie import montar_dossie, nome_execucao
from magalu_releases.extracao.texto import extrair_paginas
from magalu_releases.periodos import interpretar_periodo


@pytest.fixture
def paginas(tmp_path):
    caminho = tmp_path / "release.pdf"
    caminho.write_bytes(construir_pdf([PAGINA_TABELA, PAGINA_NARRATIVA]))
    return extrair_paginas(caminho, documento_id="doc-2t25")


@pytest.fixture
def documentos(documento_valido):
    return [
        documento_valido(
            documento_id="doc-2t25",
            periodo=interpretar_periodo("2T25"),
            titulo="Release de Resultados 2T25",
        )
    ]


class TestNomeExecucao:
    def test_carrega_empresa_n_periodos_e_hora(self):
        nome = nome_execucao(n=3, periodos=("2025-Q4", "2026-Q1", "2026-Q2"))
        assert "N3" in nome
        assert "2025-Q4" in nome or "2025Q4" in nome
        assert "magalu" in nome.lower()

    def test_duas_execucoes_nao_colidem(self):
        a = nome_execucao(n=3, periodos=("2026-Q2",), momento="20260917-183000")
        b = nome_execucao(n=3, periodos=("2026-Q2",), momento="20260917-183001")
        assert a != b

    def test_n_diferente_gera_nome_diferente(self):
        a = nome_execucao(n=2, periodos=("2026-Q2",), momento="x")
        b = nome_execucao(n=3, periodos=("2026-Q2",), momento="x")
        assert a != b


class TestDossie:
    def test_traz_texto_de_cada_pagina(self, documentos, paginas):
        texto = montar_dossie(
            run_id="run-teste", n_pedido=1, documentos=documentos,
            paginas_por_documento={"doc-2t25": paginas},
        )
        assert "Receita Liquida" in texto
        assert "Comentario da Administracao" in texto

    def test_marca_numero_de_pagina(self, documentos, paginas):
        texto = montar_dossie(
            run_id="run-teste", n_pedido=1, documentos=documentos,
            paginas_por_documento={"doc-2t25": paginas},
        )
        assert "página 1" in texto.lower()
        assert "página 2" in texto.lower()

    def test_sinaliza_pagina_com_estrutura_perdida(self, documentos, paginas):
        texto = montar_dossie(
            run_id="run-teste", n_pedido=1, documentos=documentos,
            paginas_por_documento={"doc-2t25": paginas},
        )
        assert "estrutura" in texto.lower() or "tabela" in texto.lower()

    def test_traz_o_contrato_de_saida(self, documentos, paginas):
        texto = montar_dossie(
            run_id="run-teste", n_pedido=1, documentos=documentos,
            paginas_por_documento={"doc-2t25": paginas},
        )
        for campo in ("valor_original", "trecho_fonte", "pagina", "confianca"):
            assert campo in texto

    def test_aponta_para_a_skill_sem_repetir_o_procedimento(self, documentos, paginas):
        texto = montar_dossie(
            run_id="run-teste", n_pedido=1, documentos=documentos,
            paginas_por_documento={"doc-2t25": paginas},
        )
        assert "magalu-release-analysis" in texto

    def test_identifica_documento_e_periodo(self, documentos, paginas):
        texto = montar_dossie(
            run_id="run-teste", n_pedido=1, documentos=documentos,
            paginas_por_documento={"doc-2t25": paginas},
        )
        assert "doc-2t25" in texto
        assert "2T25" in texto


class TestParser:
    def test_n_e_a_entrada_do_coletar(self):
        args = construir_parser().parse_args(["coletar", "--n", "3"])
        assert args.n == 3

    @pytest.mark.parametrize("n", ["1", "2", "7", "12"])
    def test_aceita_qualquer_n(self, n):
        assert construir_parser().parse_args(["coletar", "--n", n]).n == int(n)

    def test_n_invalido_e_recusado(self):
        with pytest.raises(SystemExit):
            construir_parser().parse_args(["coletar", "--n", "0"])

    def test_comandos_disponiveis(self):
        parser = construir_parser()
        for comando in ("coletar", "validar-fatos", "relatar"):
            assert parser.parse_args([comando] + (["--n", "1"] if comando == "coletar" else ["--run", "x"]))


class TestValidarFatosPelaCli:
    def test_fatos_validos_saem_com_codigo_zero(self, tmp_path, capsys):
        fatos = {
            "run_id": "run-teste",
            "fatos": [
                {
                    "fato_id": "f-1", "metrica_id": "receita_liquida",
                    "metrica_rotulo": "Receita Líquida", "segmento": "consolidado",
                    "base": "reportado", "periodicidade": "trimestre",
                    "tipo_valor": "absoluto", "periodo_rotulo": "2T25",
                    "valor_original": "9.856,4", "valor_normalizado": 9856.4,
                    "unidade": "R$ milhões", "documento_id": "doc-1", "pagina": 7,
                    "trecho_fonte": "Receita Líquida 9.856,4", "confianca": "alta",
                    "flags": [], "revisao_humana": False, "motivo": None,
                }
            ],
        }
        execucao = tmp_path / "run-teste"
        execucao.mkdir()
        (execucao / "fatos.json").write_text(json.dumps(fatos, ensure_ascii=False), encoding="utf-8")
        assert main(["validar-fatos", "--run", str(execucao)]) == 0

    def test_fatos_invalidos_saem_com_codigo_nao_zero(self, tmp_path, capsys):
        fatos = {"run_id": "r", "fatos": [{"fato_id": "f-1"}]}
        execucao = tmp_path / "run-teste"
        execucao.mkdir()
        (execucao / "fatos.json").write_text(json.dumps(fatos), encoding="utf-8")
        assert main(["validar-fatos", "--run", str(execucao)]) != 0

    def test_problemas_sao_listados(self, tmp_path, capsys):
        fatos = {"run_id": "r", "fatos": [{"fato_id": "f-1"}]}
        execucao = tmp_path / "run-teste"
        execucao.mkdir()
        (execucao / "fatos.json").write_text(json.dumps(fatos), encoding="utf-8")
        main(["validar-fatos", "--run", str(execucao)])
        saida = capsys.readouterr().out
        assert "obrigat" in saida.lower()

    def test_arquivo_ausente_e_erro_claro(self, tmp_path, capsys):
        execucao = tmp_path / "vazio"
        execucao.mkdir()
        assert main(["validar-fatos", "--run", str(execucao)]) != 0
        assert "fatos.json" in capsys.readouterr().out
