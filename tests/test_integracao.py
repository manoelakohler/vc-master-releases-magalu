"""Integração da Fase C: do fatos.json até a planilha auditada.

Monta uma execução completa com PDFs sintéticos, escreve os fatos como a fase de
análise escreveria, e roda `validar-fatos` e `relatar` de verdade. É o teste que
prova que as peças se encaixam — os unitários provam que cada uma está certa.

A Fase A (rede) não é exercitada aqui: teste automatizado não toca a internet.
"""

import json

import pytest
from openpyxl import load_workbook

from fixtures.pdf_sintetico import construir_pdf
from magalu_releases.cli import comando_relatar, comando_validar_fatos
from magalu_releases.config import carregar_config
from magalu_releases.extracao.texto import extrair_paginas

PAGINA_1T26 = [
    "MAGAZINE LUIZA S.A.",
    "Release de Resultados - 1T26",
    "",
    "(R$ milhoes)            1T26        1T25",
    "Receita Liquida       9.112,0     8.740,5",
    "Margem Bruta            27,6%       27,1%",
    "Prejuizo Liquido         33,9        11,2",
]

PAGINA_2T26 = [
    "MAGAZINE LUIZA S.A.",
    "Release de Resultados - 2T26",
    "",
    "(R$ milhoes)            2T26        2T25",
    "Receita Liquida       9.856,4     9.112,0",
    "Margem Bruta            27,8%       27,6%",
    "EBITDA Ajustado         988,7         n.a.",
]


def _fato(fid, metrica, rotulo, periodo, original, normalizado, unidade, doc, trecho,
          tipo_valor="absoluto", **extra):
    base = {
        "fato_id": fid,
        "metrica_id": metrica,
        "metrica_rotulo": rotulo,
        "segmento": "consolidado",
        "base": "reportado",
        "periodicidade": "trimestre",
        "tipo_valor": tipo_valor,
        "periodo_rotulo": periodo,
        "valor_original": original,
        "valor_normalizado": normalizado,
        "unidade": unidade,
        "documento_id": doc,
        "pagina": 1,
        "trecho_fonte": trecho,
        "confianca": "alta",
        "flags": [],
        "revisao_humana": False,
        "motivo": None,
    }
    base.update(extra)
    return base


@pytest.fixture
def execucao(tmp_path):
    """Monta o diretório de uma execução como a Fase A o deixaria."""
    raiz = tmp_path / "magalu_N2_2026-Q1_a_2026-Q2_20260917-190000"
    (raiz / "pdfs").mkdir(parents=True)
    (raiz / "paginas").mkdir()

    documentos = []
    for doc_id, rotulo, pagina in (
        ("doc-1t26", "1T26", PAGINA_1T26),
        ("doc-2t26", "2T26", PAGINA_2T26),
    ):
        caminho = raiz / "pdfs" / f"{doc_id}.pdf"
        caminho.write_bytes(construir_pdf([pagina]))
        paginas = extrair_paginas(caminho, documento_id=doc_id)
        (raiz / "paginas" / f"{doc_id}.json").write_text(
            json.dumps([p.__dict__ if hasattr(p, "__dict__") else {
                "documento_id": p.documento_id, "pagina": p.pagina, "texto": p.texto,
                "caracteres": p.caracteres, "tabela_suspeita": p.tabela_suspeita,
                "observacao": p.observacao,
            } for p in paginas], ensure_ascii=False),
            encoding="utf-8",
        )
        documentos.append({
            "documento_id": doc_id,
            "titulo": f"Release de Resultados {rotulo}",
            "tipo": "release_resultados",
            "periodo": {"canonico": f"2026-Q{rotulo[0]}", "rotulo": rotulo},
            "url_origem": f"https://ri.magazineluiza.com.br/x/{doc_id}.pdf",
            "data_publicacao": None,
            "arquivo_local": f"{doc_id}.pdf",
            "bytes": caminho.stat().st_size,
            "sha256": "0" * 64,
            "paginas": len(paginas),
            "textual": True,
            "baixado_em": "2026-09-17T19:00:00",
            "motivo_descarte": None,
        })

    (raiz / "documentos.json").write_text(
        json.dumps(documentos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (raiz / "manifesto.json").write_text(
        json.dumps({
            "run_id": raiz.name,
            "n_pedido": 2,
            "n_obtido": 2,
            "periodos": ["2026-Q1", "2026-Q2"],
            "fonte": "https://ri.magazineluiza.com.br/ListResultados/Central-de-Resultados",
            "pendencias": [],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fatos = [
        _fato("f-0001", "receita_liquida", "Receita Liquida", "1T26", "9.112,0", 9112.0,
              "R$ milhões", "doc-1t26", "Receita Liquida 9.112,0 8.740,5"),
        _fato("f-0002", "receita_liquida", "Receita Liquida", "2T26", "9.856,4", 9856.4,
              "R$ milhões", "doc-2t26", "Receita Liquida 9.856,4 9.112,0"),
        _fato("f-0003", "margem_bruta", "Margem Bruta", "1T26", "27,6%", 27.6, "%",
              "doc-1t26", "Margem Bruta 27,6% 27,1%", tipo_valor="percentual"),
        _fato("f-0004", "margem_bruta", "Margem Bruta", "2T26", "27,8%", 27.8, "%",
              "doc-2t26", "Margem Bruta 27,8% 27,6%", tipo_valor="percentual"),
        # Só existe no 2T26: a posição do 1T26 precisa ficar null, sem deslizar.
        _fato("f-0005", "ebitda_ajustado", "EBITDA Ajustado", "2T26", "988,7", 988.7,
              "R$ milhões", "doc-2t26", "EBITDA Ajustado 988,7 n.a.", base="ajustado"),
    ]
    (raiz / "fatos.json").write_text(
        json.dumps({"run_id": raiz.name, "fatos": fatos}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return raiz


class TestPortao:
    def test_fatos_passam_no_portao(self, execucao):
        assert comando_validar_fatos(str(execucao)) == 0

    def test_portao_barra_fato_sem_evidencia(self, execucao):
        corpo = json.loads((execucao / "fatos.json").read_text(encoding="utf-8"))
        corpo["fatos"][0]["trecho_fonte"] = "linha que nao contem o valor"
        (execucao / "fatos.json").write_text(json.dumps(corpo, ensure_ascii=False), encoding="utf-8")
        assert comando_validar_fatos(str(execucao)) != 0


class TestRelatar:
    def test_execucao_completa_aprova(self, execucao, capsys):
        codigo = comando_relatar(str(execucao), cfg=carregar_config())
        saida = capsys.readouterr().out
        assert codigo == 0, saida
        assert "Auditoria aprovada" in saida

    def test_gera_a_planilha(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        assert list(execucao.glob("analise_*.xlsx"))

    def test_gera_resumo_e_auditoria(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        assert (execucao / "resumo.md").is_file()
        assert (execucao / "auditoria.json").is_file()

    def test_resumo_gerado_nao_tem_linguagem_proibida(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        from magalu_releases.saida.resumo import validar_resumo

        assert validar_resumo((execucao / "resumo.md").read_text(encoding="utf-8")) == ()


class TestPlanilhaResultante:
    @pytest.fixture
    def planilha(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        return list(execucao.glob("analise_*.xlsx"))[0]

    def test_seis_abas(self, planilha):
        assert load_workbook(planilha).sheetnames == [
            "Resumo", "Comparativo", "Evidências", "Documentos", "Pendências", "Auditoria"
        ]

    def test_tres_series_separadas(self, planilha):
        """Receita, margem e EBITDA ajustado não se misturam."""
        aba = load_workbook(planilha)["Comparativo"]
        assert aba.max_row == 1 + 3

    def test_margem_usa_pontos_percentuais(self, planilha):
        aba = load_workbook(planilha)["Comparativo"]
        cabecalhos = [c.value for c in aba[1]]
        col_id = cabecalhos.index("serie_id") + 1
        col_pp = cabecalhos.index("variacao_pp") + 1
        col_pct = cabecalhos.index("variacao_pct") + 1
        for linha in range(2, aba.max_row + 1):
            if "margem_bruta" in str(aba.cell(row=linha, column=col_id).value):
                assert aba.cell(row=linha, column=col_pp).value == pytest.approx(0.2)
                assert aba.cell(row=linha, column=col_pct).value is None

    def test_receita_usa_variacao_percentual(self, planilha):
        aba = load_workbook(planilha)["Comparativo"]
        cabecalhos = [c.value for c in aba[1]]
        col_id = cabecalhos.index("serie_id") + 1
        col_pct = cabecalhos.index("variacao_pct") + 1
        col_pp = cabecalhos.index("variacao_pp") + 1
        for linha in range(2, aba.max_row + 1):
            if "receita_liquida" in str(aba.cell(row=linha, column=col_id).value):
                assert aba.cell(row=linha, column=col_pct).value == pytest.approx(8.166, abs=0.01)
                assert aba.cell(row=linha, column=col_pp).value is None

    def test_ebitda_ausente_no_1t26_fica_vazio(self, planilha):
        aba = load_workbook(planilha)["Comparativo"]
        cabecalhos = [c.value for c in aba[1]]
        col_id = cabecalhos.index("serie_id") + 1
        col_1t26 = cabecalhos.index("1T26") + 1
        for linha in range(2, aba.max_row + 1):
            if "ebitda" in str(aba.cell(row=linha, column=col_id).value):
                valor = aba.cell(row=linha, column=col_1t26).value
                assert valor is None
                assert valor != 0

    def test_evidencias_preservam_o_texto_do_documento(self, planilha):
        aba = load_workbook(planilha)["Evidências"]
        cabecalhos = [c.value for c in aba[1]]
        coluna = cabecalhos.index("valor_original") + 1
        originais = {aba.cell(row=r, column=coluna).value for r in range(2, aba.max_row + 1)}
        assert "9.856,4" in originais
        assert "27,8%" in originais

    def test_auditoria_sem_falha_alta(self, planilha):
        aba = load_workbook(planilha)["Auditoria"]
        cabecalhos = [c.value for c in aba[1]]
        col_resultado = cabecalhos.index("resultado") + 1
        col_severidade = cabecalhos.index("severidade") + 1
        for linha in range(2, aba.max_row + 1):
            if aba.cell(row=linha, column=col_resultado).value == "FAIL":
                assert aba.cell(row=linha, column=col_severidade).value != "alta"


class TestPendenciasDaFaseA:
    """Pendência levantada na coleta precisa chegar à entrega.

    Documento não classificado, período duplicado e lacuna trimestral são
    detectados na Fase A e gravados no manifesto. Se a Fase C não os relê, eles
    somem da planilha, do resumo e da auditoria — e a execução parece limpa.
    """

    PENDENCIA = {
        "pendencia_id": "pen-0001",
        "tipo": "conflito",
        "severidade": "alta",
        "descricao": "Período 2026-Q1 tem 2 documentos duplicados; ambos preservados",
        "referencias": ["doc-1t26", "doc-1t26-bis"],
        "valores_conflitantes": [],
        "acao_sugerida": "Confirmar qual documento é o release oficial do período",
        "status": "aberta",
    }

    def _com_pendencia(self, execucao):
        caminho = execucao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["pendencias"] = [self.PENDENCIA]
        caminho.write_text(json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")
        return execucao

    def test_pendencia_chega_na_planilha(self, execucao):
        comando_relatar(str(self._com_pendencia(execucao)), cfg=carregar_config())
        planilha = list(execucao.glob("analise_*.xlsx"))[0]
        aba = load_workbook(planilha)["Pendências"]
        textos = [
            aba.cell(row=linha, column=coluna).value
            for linha in range(2, aba.max_row + 1)
            for coluna in range(1, aba.max_column + 1)
        ]
        assert any("duplicados" in str(t) for t in textos)

    def test_pendencia_chega_no_resumo(self, execucao):
        comando_relatar(str(self._com_pendencia(execucao)), cfg=carregar_config())
        resumo = (execucao / "resumo.md").read_text(encoding="utf-8")
        assert "duplicados" in resumo

    def test_manifesto_sem_a_chave_falha_alto(self, execucao, capsys):
        caminho = execucao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        del manifesto["pendencias"]
        caminho.write_text(json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")

        codigo = comando_relatar(str(execucao), cfg=carregar_config())
        assert codigo != 0
        assert "pendencias" in capsys.readouterr().out


class TestDescartadosChegamNaAuditoria:
    """O que a seleção jogou fora precisa continuar rastreável.

    A Central mistura ITR, apresentação, transcrição e comunicado com os
    releases. O descarte é correto, mas sem registro ninguém distingue o
    documento excluído por critério do documento perdido por falha da coleta.
    """

    DESCARTADO = {
        "documento_id": "doc-itr-1t26",
        "titulo": "ITR",
        "tipo": "itr_dfp",
        "periodo": {"canonico": "2026-Q1", "rotulo": "1T26"},
        "url_origem": "https://ri.magazineluiza.com.br/x/itr-1t26.pdf",
        "data_publicacao": None,
        "arquivo_local": None,
        "bytes": None,
        "sha256": None,
        "paginas": None,
        "textual": None,
        "baixado_em": None,
        "motivo_descarte": "tipo itr_dfp não é release de resultados",
    }

    def _com_descartado(self, execucao, **ajustes):
        caminho = execucao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["descartados"] = [dict(self.DESCARTADO, **ajustes)]
        caminho.write_text(json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")
        return execucao

    def _auditoria(self, execucao):
        verificacoes = json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
        return {v["check_id"]: v for v in verificacoes}

    def test_descartado_com_motivo_aprova(self, execucao):
        comando_relatar(str(self._com_descartado(execucao)), cfg=carregar_config())
        check = self._auditoria(execucao)["sel_descartados"]
        assert check["resultado"] == "PASS"
        assert "1" in check["esperado"]

    def test_descartado_sem_motivo_reprova(self, execucao):
        comando_relatar(
            str(self._com_descartado(execucao, motivo_descarte=None)), cfg=carregar_config()
        )
        assert self._auditoria(execucao)["sel_descartados"]["resultado"] == "FAIL"

    def test_descartado_nao_entra_na_aba_documentos(self, execucao):
        """A aba Documentos descreve os PDFs analisados; o descartado não é um."""
        comando_relatar(str(self._com_descartado(execucao)), cfg=carregar_config())
        planilha = list(execucao.glob("analise_*.xlsx"))[0]
        aba = load_workbook(planilha)["Documentos"]
        ids = {aba.cell(row=linha, column=1).value for linha in range(2, aba.max_row + 1)}
        assert "doc-itr-1t26" not in ids


class TestChecksDaPlanilhaNaAuditoria:
    """A validação da planilha precisa aparecer dentro da própria planilha.

    Saindo só no terminal, ela não acompanha o arquivo: quem recebe a planilha
    não tem como saber se a releitura foi feita nem o que ela encontrou.
    """

    IDS = {"xls_abas", "xls_colunas_periodo", "xls_texto_preservado", "xls_reabertura"}

    def _aba_auditoria(self, execucao):
        planilha = list(execucao.glob("analise_*.xlsx"))[0]
        aba = load_workbook(planilha)["Auditoria"]
        cabecalhos = [c.value for c in aba[1]]
        col_id = cabecalhos.index("check_id") + 1
        col_resultado = cabecalhos.index("resultado") + 1
        return {
            aba.cell(row=linha, column=col_id).value: aba.cell(
                row=linha, column=col_resultado
            ).value
            for linha in range(2, aba.max_row + 1)
        }

    def test_os_quatro_checks_viram_linha(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        assert self.IDS <= set(self._aba_auditoria(execucao))

    def test_checks_da_planilha_passam_na_execucao_integra(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        resultados = self._aba_auditoria(execucao)
        assert all(resultados[check] == "PASS" for check in self.IDS)

    def test_auditoria_json_tambem_registra(self, execucao):
        comando_relatar(str(execucao), cfg=carregar_config())
        registrados = {
            v["check_id"]
            for v in json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
        }
        assert self.IDS <= registrados


class TestCoberturaDeclaradaNoResumo:
    """Resumo e auditoria não podem discordar sobre quanto período foi coberto.

    O documento descartado continua na aba Documentos com o motivo, mas não foi
    analisado. Contá-lo como analisado faz a planilha dizer que cobriu três
    trimestres enquanto a auditoria diz dois — e duas células do mesmo arquivo
    se contradizendo é exatamente o que esta entrega existe para evitar.
    """

    def _com_descarte(self, execucao):
        caminho = execucao / "documentos.json"
        documentos = json.loads(caminho.read_text(encoding="utf-8"))
        documentos[-1]["textual"] = False
        documentos[-1]["motivo_descarte"] = (
            "apenas 1/3 páginas com texto (mínimo 50%); sem OCR, o documento não é processado"
        )
        caminho.write_text(json.dumps(documentos, ensure_ascii=False), encoding="utf-8")
        return execucao

    def _resumo_da_planilha(self, execucao):
        planilha = list(execucao.glob("analise_*.xlsx"))[0]
        aba = load_workbook(planilha)["Resumo"]
        return {
            aba.cell(row=linha, column=1).value: aba.cell(row=linha, column=2).value
            for linha in range(1, aba.max_row + 1)
        }

    def test_planilha_declara_n_obtido_sem_o_descartado(self, execucao):
        comando_relatar(str(self._com_descarte(execucao)), cfg=carregar_config())
        assert self._resumo_da_planilha(execucao)["N obtido"] == 1

    def test_planilha_avisa_que_faltou_release(self, execucao):
        comando_relatar(str(self._com_descarte(execucao)), cfg=carregar_config())
        planilha = list(execucao.glob("analise_*.xlsx"))[0]
        aba = load_workbook(planilha)["Resumo"]
        textos = [aba.cell(row=linha, column=1).value for linha in range(1, aba.max_row + 1)]
        assert any("ATENÇÃO" in str(t) for t in textos)

    def test_resumo_md_concorda_com_a_auditoria(self, execucao):
        comando_relatar(str(self._com_descarte(execucao)), cfg=carregar_config())
        resumo = (execucao / "resumo.md").read_text(encoding="utf-8")
        assert "Releases pedidos: 2. Releases analisados: 1." in resumo

        auditoria = {
            v["check_id"]: v
            for v in json.loads((execucao / "auditoria.json").read_text(encoding="utf-8"))
        }
        assert auditoria["sel_quantidade"]["obtido"] == "1"


class TestReguaDePeriodosUnica:
    """A régua da comparação não admite período repetido.

    Manifesto com canônico duplicado produzia duas colunas idênticas no
    Comparativo, e todos os checks passavam: a contagem batia com a régua
    torta. Como o manifesto é escrito por máquina, repetição ali significa
    coleta antiga ou corrompida — e isso se declara, não se conserta em
    silêncio por baixo de uma análise já escrita contra aquele dossiê.
    """

    def _com_periodo_repetido(self, execucao):
        caminho = execucao / "manifesto.json"
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        manifesto["periodos"] = ["2026-Q1", "2026-Q2", "2026-Q2"]
        caminho.write_text(json.dumps(manifesto, ensure_ascii=False), encoding="utf-8")
        return execucao

    def test_periodo_repetido_no_manifesto_falha_alto(self, execucao, capsys):
        codigo = comando_relatar(str(self._com_periodo_repetido(execucao)), cfg=carregar_config())
        saida = capsys.readouterr().out
        assert codigo != 0
        assert "2026-Q2" in saida

    def test_nao_gera_planilha_com_coluna_repetida(self, execucao):
        comando_relatar(str(self._com_periodo_repetido(execucao)), cfg=carregar_config())
        assert not list(execucao.glob("analise_*.xlsx"))

    def test_regua_integra_continua_passando(self, execucao):
        assert comando_relatar(str(execucao), cfg=carregar_config()) == 0

