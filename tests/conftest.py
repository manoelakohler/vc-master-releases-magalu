"""Fábricas compartilhadas de objetos de domínio válidos.

Os testes partem de um objeto correto e quebram uma invariante por vez — assim
cada falha aponta para exatamente uma regra.
"""

import pytest

from magalu_releases.models import Documento, Fato
from magalu_releases.periodos import interpretar_periodo
from magalu_releases.vocabularios import (
    Base,
    Confianca,
    Periodicidade,
    Segmento,
    TipoDocumento,
    TipoValor,
)


@pytest.fixture
def periodo_2t25():
    return interpretar_periodo("2T25")


@pytest.fixture
def fato_valido(periodo_2t25):
    def construir(**alteracoes):
        padrao = dict(
            fato_id="f-0001",
            metrica_id="receita_liquida",
            metrica_rotulo="Receita Líquida",
            segmento=Segmento.CONSOLIDADO,
            base=Base.REPORTADO,
            periodicidade=Periodicidade.TRIMESTRE,
            tipo_valor=TipoValor.ABSOLUTO,
            periodo=periodo_2t25,
            valor_original="9.856,4",
            valor_normalizado=9856.4,
            unidade="R$ milhões",
            documento_id="doc-2t25",
            pagina=7,
            trecho_fonte="Receita Líquida 9.856,4 10.112,0",
            confianca=Confianca.ALTA,
            flags=(),
            revisao_humana=False,
            motivo=None,
        )
        padrao.update(alteracoes)
        return Fato(**padrao)

    return construir


@pytest.fixture
def documento_valido(periodo_2t25):
    def construir(**alteracoes):
        padrao = dict(
            documento_id="doc-2t25",
            titulo="Release de Resultados 2T25",
            tipo=TipoDocumento.RELEASE_RESULTADOS,
            periodo=periodo_2t25,
            url_origem="https://ri.magazineluiza.com.br/algum/release-2t25.pdf",
            data_publicacao="2025-08-14",
            arquivo_local="pdfs/doc-2t25.pdf",
            bytes=1_234_567,
            sha256="a" * 64,
            paginas=22,
            textual=True,
            baixado_em="2026-09-17T18:30:00",
            motivo_descarte=None,
        )
        padrao.update(alteracoes)
        return Documento(**padrao)

    return construir
