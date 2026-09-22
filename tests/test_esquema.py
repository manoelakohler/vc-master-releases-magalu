"""O portão semântico: validação do arquivo de fatos.

Este é o único caminho pelo qual valor semântico entra no pipeline. Ele recusa
tudo que não satisfaz o contrato e relata **todos** os problemas de uma vez —
parar no primeiro faria a correção virar um jogo de tentativa e erro.
"""

import json

import pytest

from magalu_releases.fatos.esquema import FatosInvalidos, carregar_fatos, serializar_fatos


def fato_bruto(**alteracoes):
    padrao = {
        "fato_id": "f-0001",
        "metrica_id": "receita_liquida",
        "metrica_rotulo": "Receita Líquida",
        "segmento": "consolidado",
        "base": "reportado",
        "periodicidade": "trimestre",
        "tipo_valor": "absoluto",
        "periodo_rotulo": "2T25",
        "valor_original": "9.856,4",
        "valor_normalizado": 9856.4,
        "unidade": "R$ milhões",
        "documento_id": "doc-2t25",
        "pagina": 7,
        "trecho_fonte": "Receita Líquida 9.856,4 9.112,0",
        "confianca": "alta",
        "flags": [],
        "revisao_humana": False,
        "motivo": None,
    }
    padrao.update(alteracoes)
    return padrao


def escrever(tmp_path, fatos, **extra):
    caminho = tmp_path / "fatos.json"
    corpo = {"run_id": "run-teste", "fatos": fatos}
    corpo.update(extra)
    caminho.write_text(json.dumps(corpo, ensure_ascii=False), encoding="utf-8")
    return caminho


class TestCargaValida:
    def test_carrega_fato_correto(self, tmp_path):
        r = carregar_fatos(escrever(tmp_path, [fato_bruto()]))
        assert len(r.fatos) == 1
        assert r.problemas == ()

    def test_periodo_vira_objeto_canonico(self, tmp_path):
        r = carregar_fatos(escrever(tmp_path, [fato_bruto()]))
        assert r.fatos[0].periodo.canonico == "2025-Q2"

    def test_enums_sao_convertidos(self, tmp_path):
        from magalu_releases.vocabularios import Base, Segmento

        r = carregar_fatos(escrever(tmp_path, [fato_bruto()]))
        assert r.fatos[0].segmento is Segmento.CONSOLIDADO
        assert r.fatos[0].base is Base.REPORTADO

    def test_varios_fatos(self, tmp_path):
        fatos = [fato_bruto(fato_id=f"f-{i:04d}") for i in range(5)]
        assert len(carregar_fatos(escrever(tmp_path, fatos)).fatos) == 5


class TestVocabulario:
    @pytest.mark.parametrize(
        "campo,valor",
        [
            ("segmento", "varejo"),
            ("base", "pro_forma"),
            ("periodicidade", "semestre"),
            ("tipo_valor", "razao"),
            ("confianca", "altissima"),
        ],
    )
    def test_valor_fora_do_vocabulario_e_recusado(self, tmp_path, campo, valor):
        r = carregar_fatos(escrever(tmp_path, [fato_bruto(**{campo: valor})]), estrito=False)
        assert any(campo in p for p in r.problemas)

    def test_flag_invalida_e_recusada(self, tmp_path):
        r = carregar_fatos(
            escrever(tmp_path, [fato_bruto(flags=["chute"], revisao_humana=True)]), estrito=False
        )
        assert r.problemas


class TestInvariantes:
    def test_evidencia_faltando_e_recusada(self, tmp_path):
        r = carregar_fatos(escrever(tmp_path, [fato_bruto(trecho_fonte="")]), estrito=False)
        assert any("trecho" in p.lower() for p in r.problemas)

    def test_trecho_que_nao_contem_o_valor_e_recusado(self, tmp_path):
        r = carregar_fatos(
            escrever(tmp_path, [fato_bruto(trecho_fonte="Outra linha 1.111,1")]), estrito=False
        )
        assert any("trecho" in p.lower() for p in r.problemas)

    def test_zero_no_lugar_de_nulo_e_recusado(self, tmp_path):
        """Unidade ausente com valor normalizado preenchido viola o contrato."""
        r = carregar_fatos(
            escrever(tmp_path, [fato_bruto(unidade=None, valor_normalizado=0.0)]), estrito=False
        )
        assert any("unidade" in p.lower() for p in r.problemas)

    def test_periodo_indeterminado_e_recusado(self, tmp_path):
        r = carregar_fatos(
            escrever(tmp_path, [fato_bruto(periodo_rotulo="quando der")]), estrito=False
        )
        assert any("per" in p.lower() for p in r.problemas)

    def test_campo_obrigatorio_ausente_e_recusado(self, tmp_path):
        incompleto = fato_bruto()
        del incompleto["documento_id"]
        r = carregar_fatos(escrever(tmp_path, [incompleto]), estrito=False)
        assert any("documento_id" in p for p in r.problemas)


class TestRelatorioDeProblemas:
    def test_relata_todos_os_problemas_de_uma_vez(self, tmp_path):
        ruins = [
            fato_bruto(fato_id="f-1", segmento="varejo"),
            fato_bruto(fato_id="f-2", trecho_fonte=""),
            fato_bruto(fato_id="f-3", confianca="altissima"),
        ]
        r = carregar_fatos(escrever(tmp_path, ruins), estrito=False)
        assert len(r.problemas) >= 3

    def test_problema_identifica_o_fato(self, tmp_path):
        r = carregar_fatos(
            escrever(tmp_path, [fato_bruto(fato_id="f-042", trecho_fonte="")]), estrito=False
        )
        assert any("f-042" in p or "[0]" in p for p in r.problemas)

    def test_modo_estrito_levanta_excecao(self, tmp_path):
        with pytest.raises(FatosInvalidos):
            carregar_fatos(escrever(tmp_path, [fato_bruto(trecho_fonte="")]))

    def test_fato_id_duplicado_e_problema(self, tmp_path):
        fatos = [fato_bruto(fato_id="f-igual"), fato_bruto(fato_id="f-igual")]
        r = carregar_fatos(escrever(tmp_path, fatos), estrito=False)
        assert any("duplic" in p.lower() for p in r.problemas)


class TestArquivo:
    def test_arquivo_inexistente_falha_alto(self, tmp_path):
        with pytest.raises(FatosInvalidos):
            carregar_fatos(tmp_path / "nao-existe.json")

    def test_json_invalido_falha_alto(self, tmp_path):
        ruim = tmp_path / "fatos.json"
        ruim.write_text("{isto nao e json", encoding="utf-8")
        with pytest.raises(FatosInvalidos):
            carregar_fatos(ruim)

    def test_sem_a_chave_fatos_falha_alto(self, tmp_path):
        ruim = tmp_path / "fatos.json"
        ruim.write_text(json.dumps({"run_id": "x"}), encoding="utf-8")
        with pytest.raises(FatosInvalidos):
            carregar_fatos(ruim)


class TestIdaEVolta:
    def test_serializa_e_recarrega_sem_perda(self, tmp_path):
        original = carregar_fatos(escrever(tmp_path, [fato_bruto()])).fatos
        destino = tmp_path / "saida.json"
        destino.write_text(
            json.dumps(
                {"run_id": "run-teste", "fatos": serializar_fatos(original)}, ensure_ascii=False
            ),
            encoding="utf-8",
        )
        recarregado = carregar_fatos(destino).fatos
        assert recarregado[0].valor_original == original[0].valor_original
        assert recarregado[0].periodo.canonico == original[0].periodo.canonico
        assert recarregado[0].trecho_fonte == original[0].trecho_fonte
