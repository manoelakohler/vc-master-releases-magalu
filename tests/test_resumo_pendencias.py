"""Esqueleto factual do resumo, validação de linguagem e consolidação de pendências.

O texto do resumo é escrito na fase de análise, guiada pela skill. O que o
código faz é montar o esqueleto com os fatos já apurados e recusar linguagem
que soe como recomendação — duas tarefas determinísticas.
"""

import pytest

from magalu_releases.models import Pendencia, PontoSerie, Serie, Variacao
from magalu_releases.saida.pendencias import consolidar_pendencias
from magalu_releases.saida.resumo import SECOES, montar_esqueleto, validar_resumo
from magalu_releases.vocabularios import (
    Base,
    BaseComparacao,
    Confianca,
    Gatilho,
    Periodicidade,
    Segmento,
    Severidade,
    TipoValor,
)

PERIODOS = ("2025-Q4", "2026-Q1", "2026-Q2")
ROTULOS = {"2025-Q4": "4T25", "2026-Q1": "1T26", "2026-Q2": "2T26"}


def serie_exemplo(valores=(9112.0, None, 9856.4), tipo=TipoValor.ABSOLUTO, unidade="R$ milhões"):
    return Serie(
        serie_id="receita_liquida-consolidado-reportado-trimestre-absoluto",
        metrica_id="receita_liquida",
        metrica_rotulo="Receita Líquida",
        segmento=Segmento.CONSOLIDADO,
        base=Base.REPORTADO,
        periodicidade=Periodicidade.TRIMESTRE,
        tipo_valor=tipo,
        unidade_serie=unidade,
        pontos=tuple(
            PontoSerie(c, f"f-{c}" if v is not None else None, v, str(v) if v is not None else None)
            for c, v in zip(PERIODOS, valores)
        ),
        confianca_minima=Confianca.ALTA,
    )


class TestEsqueleto:
    def test_tem_as_seis_secoes(self):
        texto = montar_esqueleto(
            n_pedido=3, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[], pendencias=[], documentos=[],
        )
        for secao in SECOES:
            assert secao in texto

    def test_declara_n_pedido_e_obtido(self):
        texto = montar_esqueleto(
            n_pedido=5, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[], pendencias=[], documentos=[],
        )
        assert "5" in texto and "3" in texto

    def test_periodos_em_ordem_crescente(self):
        texto = montar_esqueleto(
            n_pedido=3, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[], pendencias=[], documentos=[],
        )
        assert texto.index("4T25") < texto.index("1T26") < texto.index("2T26")

    def test_lacuna_e_declarada_em_vez_de_contornada(self):
        texto = montar_esqueleto(
            n_pedido=3, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[], pendencias=[], documentos=[],
        )
        assert "1T26" in texto
        assert "ausente" in texto.lower() or "não reportado" in texto.lower()

    def test_valores_aparecem_com_unidade(self):
        texto = montar_esqueleto(
            n_pedido=3, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[], pendencias=[], documentos=[],
        )
        assert "R$ milhões" in texto

    def test_variacao_suprimida_explica_o_motivo(self):
        variacao = Variacao(
            serie_id=serie_exemplo().serie_id,
            periodo_de="2025-Q4",
            periodo_para="2026-Q1",
            base_comparacao=BaseComparacao.PERIODO_ANTERIOR,
            calculada=False,
            motivo_nao_calculada="valor ausente em 2026-Q1",
        )
        texto = montar_esqueleto(
            n_pedido=3, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[variacao], pendencias=[], documentos=[],
        )
        assert "ausente" in texto.lower()

    def test_esqueleto_nao_contem_linguagem_proibida(self):
        texto = montar_esqueleto(
            n_pedido=3, periodos=PERIODOS, rotulos=ROTULOS, series=[serie_exemplo()],
            variacoes=[], pendencias=[], documentos=[],
        )
        assert validar_resumo(texto) == ()


class TestValidacaoDoResumo:
    def test_recusa_recomendacao(self):
        assert validar_resumo("Recomendamos a compra das ações.")

    def test_recusa_adjetivacao(self):
        assert validar_resumo("Resultado sólido no trimestre.")

    def test_aceita_texto_factual(self):
        texto = "A receita líquida passou de 9.112,0 em 4T25 para 9.856,4 em 2T26 (R$ milhões)."
        assert validar_resumo(texto) == ()

    def test_aceita_metrica_de_vendas(self):
        assert validar_resumo("As vendas totais somaram R$ 14.200,0 milhões.") == ()

    def test_relata_o_trecho_problematico(self):
        problemas = validar_resumo("O investidor deve comprar ações da companhia.")
        assert any("compr" in p.lower() for p in problemas)


class TestConsolidacaoDePendencias:
    def _pendencia(self, pid, severidade, tipo=Gatilho.CONFLITO, descricao="x"):
        return Pendencia(
            pendencia_id=pid, tipo=tipo, severidade=severidade, descricao=descricao
        )

    def test_junta_grupos(self):
        a = [self._pendencia("p1", Severidade.BAIXA)]
        b = [self._pendencia("p2", Severidade.ALTA)]
        assert len(consolidar_pendencias(a, b)) == 2

    def test_renumera_de_forma_estavel(self):
        a = [self._pendencia("p1", Severidade.ALTA)]
        b = [self._pendencia("p1", Severidade.MEDIA)]
        ids = [p.pendencia_id for p in consolidar_pendencias(a, b)]
        assert len(set(ids)) == 2

    def test_ordena_por_severidade_decrescente(self):
        entrada = [
            self._pendencia("p1", Severidade.BAIXA),
            self._pendencia("p2", Severidade.ALTA),
            self._pendencia("p3", Severidade.MEDIA),
        ]
        severidades = [p.severidade for p in consolidar_pendencias(entrada)]
        assert severidades == [Severidade.ALTA, Severidade.MEDIA, Severidade.BAIXA]

    def test_remove_duplicata_identica(self):
        igual = self._pendencia("p1", Severidade.ALTA, descricao="mesma coisa")
        outra = self._pendencia("p9", Severidade.ALTA, descricao="mesma coisa")
        assert len(consolidar_pendencias([igual], [outra])) == 1

    def test_nada_a_consolidar(self):
        assert consolidar_pendencias() == ()
