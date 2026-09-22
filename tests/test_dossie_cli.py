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


class TestColetaRegistraPendencia:
    """O que a coleta perde precisa ficar visível na entrega.

    PDF sem camada de texto e download que falhou hoje só produziam um aviso no
    terminal. Aviso em terminal não chega à planilha: a execução segue com um
    período a menos e nada na entrega diz por quê.
    """

    @staticmethod
    def _cliente(pdfs, falhar=(), nomes=None):
        """Serve a home, a Central e os PDFs — o caminho real da coleta.

        `nomes` é o que o servidor devolve em Content-Disposition; por padrão
        cada PDF vem nomeado como o release do seu período.
        """
        from fixtures.central_sintetica import HTML_CENTRAL, HTML_HOME
        from magalu_releases.fonte.http import FalhaHttp

        nomes = nomes or {}

        class RespostaFalsa:
            def __init__(self, conteudo, content_type, nome=None):
                self.status = 200
                self.url_final = "https://ri.magazineluiza.com.br/"
                self.conteudo = conteudo
                self.content_type = content_type
                self.cabecalhos = (
                    {"Content-Disposition": f'inline; filename="{nome}"'} if nome else {}
                )
                self.nome_arquivo = nome

        class ClienteFalso:
            def obter(self, url, referer=None):
                if url.rstrip("/").endswith("magazineluiza.com.br"):
                    return RespostaFalsa(HTML_HOME.encode("utf-8"), "text/html")
                if "ListResultados" in url:
                    return RespostaFalsa(HTML_CENTRAL.encode("utf-8"), "text/html")
                for token, conteudo in pdfs.items():
                    if token in url:
                        if token in falhar:
                            raise FalhaHttp(f"HTTP 403 em {url}")
                        nome = nomes.get(token, f"MGLU_ER_{token.split('-')[-1]}_POR.pdf")
                        return RespostaFalsa(conteudo, "application/pdf", nome)
                raise FalhaHttp(f"HTTP 404 em {url}")

        return ClienteFalso()

    @staticmethod
    def _pendencias(raiz):
        execucao = next(raiz.iterdir())
        manifesto = json.loads((execucao / "manifesto.json").read_text(encoding="utf-8"))
        return manifesto["pendencias"]

    def test_pdf_nao_textual_vira_pendencia(self, tmp_path):
        from magalu_releases.cli import comando_coletar
        from magalu_releases.config import carregar_config

        cliente = self._cliente({"TOKEN-RELEASE-2T26": construir_pdf([[""]])})
        comando_coletar(1, cfg=carregar_config(), cliente=cliente, raiz=tmp_path)

        pendencias = self._pendencias(tmp_path)
        assert any("textual" in p["descricao"].lower() for p in pendencias)
        assert any(
            "textual" in p["descricao"].lower() and p["severidade"] == "alta"
            for p in pendencias
        )

    def test_download_que_falha_vira_pendencia(self, tmp_path):
        from magalu_releases.cli import comando_coletar
        from magalu_releases.config import carregar_config

        cliente = self._cliente(
            {"TOKEN-RELEASE-2T26": construir_pdf([PAGINA_TABELA])},
            falhar={"TOKEN-RELEASE-2T26"},
        )
        comando_coletar(1, cfg=carregar_config(), cliente=cliente, raiz=tmp_path)

        pendencias = self._pendencias(tmp_path)
        assert any("403" in p["descricao"] or "baixado" in p["descricao"].lower()
                   for p in pendencias)

    def test_coleta_integra_nao_inventa_pendencia_de_coleta(self, tmp_path):
        from magalu_releases.cli import comando_coletar
        from magalu_releases.config import carregar_config

        cliente = self._cliente({"TOKEN-RELEASE-2T26": construir_pdf([PAGINA_TABELA])})
        comando_coletar(1, cfg=carregar_config(), cliente=cliente, raiz=tmp_path)

        descricoes = " ".join(p["descricao"].lower() for p in self._pendencias(tmp_path))
        assert "textual" not in descricoes
        assert "não pôde ser baixado" not in descricoes


class TestColetaRegistraDescartados:
    """A Fase A precisa entregar à Fase C o que descartou, com o motivo."""

    def test_manifesto_traz_os_descartados_com_motivo(self, tmp_path):
        from magalu_releases.cli import comando_coletar
        from magalu_releases.config import carregar_config

        cliente = TestColetaRegistraPendencia._cliente(
            {"TOKEN-RELEASE-2T26": construir_pdf([PAGINA_TABELA])}
        )
        comando_coletar(1, cfg=carregar_config(), cliente=cliente, raiz=tmp_path)

        execucao = next(tmp_path.iterdir())
        manifesto = json.loads((execucao / "manifesto.json").read_text(encoding="utf-8"))
        descartados = manifesto["descartados"]
        assert descartados, "a Central sintética tem ITR e apresentação para descartar"
        assert all(d["motivo_descarte"] for d in descartados)
        assert any(d["tipo"] == "itr_dfp" for d in descartados)


class TestConfirmacaoDoReleaseNoDownload:
    """O que o servidor nomeia manda sobre o que a listagem prometia.

    O link da Central é um token opaco. Se o arquivo que volta se identifica
    como outro documento — ou como outro período — seguir em frente colocaria
    números do documento errado na planilha, com evidência apontando para um
    release que nunca foi lido.
    """

    def _coletar(self, tmp_path, nome_devolvido):
        from magalu_releases.cli import comando_coletar
        from magalu_releases.config import carregar_config

        cliente = TestColetaRegistraPendencia._cliente(
            {"TOKEN-RELEASE-2T26": construir_pdf([PAGINA_TABELA])},
            nomes={"TOKEN-RELEASE-2T26": nome_devolvido},
        )
        comando_coletar(1, cfg=carregar_config(), cliente=cliente, raiz=tmp_path)
        execucao = next(tmp_path.iterdir())
        return execucao, json.loads((execucao / "manifesto.json").read_text(encoding="utf-8"))

    def test_documento_de_outro_tipo_vira_pendencia(self, tmp_path):
        execucao, manifesto = self._coletar(
            tmp_path, "2T26 - Demonstrações Financeiras (DFS) - Magalu.pdf"
        )
        assert any("não se identifica como release" in p["descricao"]
                   for p in manifesto["pendencias"])

    def test_documento_de_outro_periodo_vira_pendencia(self, tmp_path):
        execucao, manifesto = self._coletar(tmp_path, "MGLU_ER_4T25_POR.pdf")
        assert any("4T25" in p["descricao"] and "2T26" in p["descricao"]
                   for p in manifesto["pendencias"])

    def test_documento_nao_confirmado_nao_entra_no_dossie(self, tmp_path):
        execucao, _ = self._coletar(tmp_path, "MGLU_ER_4T25_POR.pdf")
        dossie = (execucao / "dossie.md").read_text(encoding="utf-8")
        assert "Texto extraído" in dossie
        assert "Receita Liquida" not in dossie

    def test_release_confirmado_assume_o_nome_do_servidor(self, tmp_path):
        execucao, _ = self._coletar(tmp_path, "MGLU_ER_2T26_POR.pdf")
        documentos = json.loads((execucao / "documentos.json").read_text(encoding="utf-8"))
        assert documentos[0]["titulo"] == "MGLU_ER_2T26_POR.pdf"
        assert documentos[0]["nome_servidor"] == "MGLU_ER_2T26_POR.pdf"
