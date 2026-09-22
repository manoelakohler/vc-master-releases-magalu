"""Seleção dos N releases mais recentes.

Precisa funcionar para N=1, N=3 e N=12 sem tratamento especial. Se algo só
funciona para um N, isso é defeito — não configuração.
"""

import pytest

from magalu_releases.fonte.selecao import SelecaoInvalida, selecionar_releases
from magalu_releases.periodos import interpretar_periodo
from magalu_releases.vocabularios import TipoDocumento as TD


def doc(documento_valido, rotulo, tipo=TD.RELEASE_RESULTADOS, **extra):
    periodo = interpretar_periodo(rotulo) if rotulo else None
    return documento_valido(
        documento_id=f"doc-{rotulo or 'sem-periodo'}-{extra.get('sufixo', '')}".rstrip("-"),
        titulo=f"Release de Resultados {rotulo}",
        tipo=tipo,
        periodo=periodo,
        **{k: v for k, v in extra.items() if k != "sufixo"},
    )


@pytest.fixture
def universo(documento_valido):
    rotulos = ["1T25", "2T25", "3T25", "4T25", "1T26", "2T26"]
    return [doc(documento_valido, r) for r in rotulos]


class TestQuantidadeN:
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
    def test_seleciona_exatamente_n(self, universo, n):
        r = selecionar_releases(universo, n)
        assert r.n_obtido == n
        assert len(r.selecionados) == n

    def test_pega_os_mais_recentes(self, universo):
        r = selecionar_releases(universo, 3)
        assert [d.periodo.canonico for d in r.selecionados] == [
            "2025-Q4",
            "2026-Q1",
            "2026-Q2",
        ]

    def test_ordem_e_cronologica_crescente(self, universo):
        r = selecionar_releases(universo, 4)
        canonicos = [d.periodo.canonico for d in r.selecionados]
        assert canonicos == sorted(canonicos)

    def test_n_maior_que_o_disponivel_entrega_o_que_existe(self, universo):
        r = selecionar_releases(universo, 99)
        assert r.n_pedido == 99
        assert r.n_obtido == len(universo)
        assert r.n_obtido < r.n_pedido

    def test_diferenca_entre_pedido_e_obtido_e_declarada(self, universo):
        r = selecionar_releases(universo, 99)
        assert r.faltou_documento is True

    @pytest.mark.parametrize("n", [0, -1, -10])
    def test_n_invalido_falha_alto(self, universo, n):
        with pytest.raises(SelecaoInvalida):
            selecionar_releases(universo, n)


class TestFiltragem:
    def test_descarta_nao_releases(self, documento_valido, universo):
        ruido = [
            doc(documento_valido, "2T26", TD.ITR_DFP, sufixo="itr"),
            doc(documento_valido, "2T26", TD.APRESENTACAO, sufixo="apr"),
            doc(documento_valido, "2T26", TD.TRANSCRICAO, sufixo="tra"),
        ]
        r = selecionar_releases(universo + ruido, 2)
        ids = {d.documento_id for d in r.selecionados}
        assert all("itr" not in i and "apr" not in i and "tra" not in i for i in ids)
        assert len(r.descartados) >= 3

    def test_descartados_registram_motivo(self, documento_valido, universo):
        r = selecionar_releases(universo + [doc(documento_valido, "2T26", TD.ITR_DFP, sufixo="itr")], 2)
        assert all(d.motivo_descarte for d in r.descartados)

    def test_documento_sem_periodo_vira_pendencia(self, documento_valido, universo):
        sem_periodo = documento_valido(
            documento_id="doc-sem-periodo",
            titulo="Release de Resultados",
            tipo=TD.RELEASE_RESULTADOS,
            periodo=None,
        )
        r = selecionar_releases(universo + [sem_periodo], 2)
        assert any("periodo" in p.descricao.lower() for p in r.pendencias)
        assert "doc-sem-periodo" not in {d.documento_id for d in r.selecionados}

    def test_nao_classificado_nunca_entra(self, documento_valido, universo):
        nc = doc(documento_valido, "2T26", TD.NAO_CLASSIFICADO, sufixo="nc")
        r = selecionar_releases(universo + [nc], 1)
        assert "nc" not in "".join(d.documento_id for d in r.selecionados)


class TestDuplicatasELacunas:
    def test_periodo_duplicado_abre_pendencia_sem_escolher(self, documento_valido, universo):
        gemeo = doc(documento_valido, "2T26", sufixo="b")
        r = selecionar_releases(universo + [gemeo], 2)
        assert any("duplic" in p.descricao.lower() for p in r.pendencias)

    def test_duplicata_preserva_os_dois_documentos(self, documento_valido, universo):
        gemeo = doc(documento_valido, "2T26", sufixo="b")
        r = selecionar_releases(universo + [gemeo], 1)
        pend = [p for p in r.pendencias if "duplic" in p.descricao.lower()]
        assert pend and len(pend[0].referencias) >= 2

    def test_lacuna_na_sequencia_e_sinalizada(self, documento_valido):
        docs = [doc(documento_valido, r) for r in ["1T25", "2T25", "4T25"]]
        r = selecionar_releases(docs, 3)
        assert r.n_obtido == 3
        assert any("lacuna" in p.descricao.lower() for p in r.pendencias)

    def test_sequencia_completa_nao_gera_alarme_falso(self, universo):
        r = selecionar_releases(universo, 3)
        assert not any("lacuna" in p.descricao.lower() for p in r.pendencias)


class TestListaVazia:
    def test_nenhum_release_disponivel(self):
        r = selecionar_releases([], 3)
        assert r.n_obtido == 0
        assert r.selecionados == ()
        assert r.faltou_documento is True
