"""Agrupamento dos fatos em séries comparáveis.

Uma série é o conjunto de fatos que compartilham a tupla de identidade inteira.
Se dois fatos não compartilham a tupla, eles não pertencem à mesma série e não
se comparam — nem "só para ilustrar".

A série tem sempre N posições, uma por período analisado, em ordem crescente.
Período sem fato é uma posição com None. Fazer a lista encolher, ou deslizar os
valores para tapar o buraco, é como uma série inteira passa a comparar períodos
errados sem que nada pareça estranho.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from magalu_releases.models import Fato, Pendencia, PontoSerie, Serie, chave_serie
from magalu_releases.numeros import FATORES_MONETARIOS, EscalaIncompativel, converter_escala
from magalu_releases.vocabularios import Confianca, Gatilho, Severidade, pior_confianca

_TOLERANCIA = 1e-9


@dataclass(frozen=True, slots=True)
class ResultadoSeries:
    series: tuple[Serie, ...]
    pendencias: tuple[Pendencia, ...]


def _identificador(chave) -> str:
    metrica, segmento, base, periodicidade, tipo_valor = chave
    return "-".join([metrica, segmento.value, base.value, periodicidade.value, tipo_valor.value])


def _escolher_unidade(fatos: list[Fato]) -> tuple[str | None, bool]:
    """Escolhe a escala única da série. O segundo retorno indica incompatibilidade.

    A referência é a unidade do ponto mais recente: é a que o leitor vê primeiro
    e a que corresponde ao release mais atual.
    """
    unidades = [f.unidade for f in fatos if f.unidade is not None]
    if not unidades:
        return None, False

    distintas = set(unidades)
    if len(distintas) == 1:
        return unidades[0], False

    if distintas <= set(FATORES_MONETARIOS):
        mais_recente = max(fatos, key=lambda f: f.periodo.chave_ordenacao)
        return mais_recente.unidade, False

    return None, True


def construir_series(fatos, periodos) -> ResultadoSeries:
    """Agrupa os fatos e devolve uma série por chave, com N posições cada."""
    periodos = tuple(periodos)
    agrupados: dict[tuple, list[Fato]] = {}
    for fato in fatos:
        agrupados.setdefault(chave_serie(fato), []).append(fato)

    series: list[Serie] = []
    pendencias: list[Pendencia] = []
    contador = 0

    def nova_pendencia(tipo, severidade, descricao, referencias, acao, conflitantes=()):
        nonlocal contador
        contador += 1
        return Pendencia(
            pendencia_id=f"pen-s{contador:04d}",
            tipo=tipo,
            severidade=severidade,
            descricao=descricao,
            referencias=tuple(referencias),
            valores_conflitantes=tuple(conflitantes),
            acao_sugerida=acao,
        )

    for chave, do_grupo in agrupados.items():
        serie_id = _identificador(chave)
        metrica_id, segmento, base, periodicidade, tipo_valor = chave
        unidade_serie, incompativel = _escolher_unidade(do_grupo)

        if incompativel:
            pendencias.append(
                nova_pendencia(
                    Gatilho.UNIDADE_NAO_CLARA,
                    Severidade.ALTA,
                    f"Série {serie_id!r} mistura unidades não convertíveis "
                    f"({sorted({f.unidade for f in do_grupo if f.unidade})}); "
                    "os valores não foram unificados",
                    [f.fato_id for f in do_grupo],
                    "Confirmar a unidade correta de cada período no documento de origem",
                )
            )

        por_periodo: dict[str, list[Fato]] = {}
        for fato in do_grupo:
            por_periodo.setdefault(fato.periodo.canonico, []).append(fato)

        pontos: list[PontoSerie] = []
        usados: list[Fato] = []

        for canonico in periodos:
            candidatos = por_periodo.get(canonico, [])
            if not candidatos:
                pontos.append(PontoSerie(canonico, None, None, None))
                continue

            # Reapresentação entre releases: os dois lados ficam, nenhum vence.
            distintos = {
                f.valor_normalizado for f in candidatos if f.valor_normalizado is not None
            }
            if len(candidatos) > 1 and len(distintos) > 1:
                pendencias.append(
                    nova_pendencia(
                        Gatilho.CONFLITO,
                        Severidade.ALTA,
                        f"Período {canonico} da série {serie_id!r} tem valores divergentes "
                        "entre documentos (possível reapresentação); nenhum foi escolhido",
                        [f.fato_id for f in candidatos],
                        "Comparar os documentos e decidir qual valor usar",
                        [
                            f"{f.documento_id} p.{f.pagina}: {f.valor_original}"
                            for f in candidatos
                        ],
                    )
                )

            escolhido = candidatos[0]
            usados.append(escolhido)
            valor = escolhido.valor_normalizado

            if (
                valor is not None
                and unidade_serie
                and escolhido.unidade
                and escolhido.unidade != unidade_serie
            ):
                try:
                    valor = converter_escala(valor, escolhido.unidade, unidade_serie)
                except EscalaIncompativel:
                    valor = None

            pontos.append(
                PontoSerie(
                    periodo_canonico=canonico,
                    fato_id=escolhido.fato_id,
                    valor_normalizado=valor,
                    valor_original=escolhido.valor_original,
                )
            )

        confiancas = [f.confianca for f in usados]
        confianca_minima = pior_confianca(*confiancas) if confiancas else None
        precisa_revisao = (
            incompativel
            or any(f.revisao_humana for f in usados)
            or confianca_minima is Confianca.BAIXA
        )

        series.append(
            Serie(
                serie_id=serie_id,
                metrica_id=metrica_id,
                metrica_rotulo=do_grupo[0].metrica_rotulo,
                segmento=segmento,
                base=base,
                periodicidade=periodicidade,
                tipo_valor=tipo_valor,
                unidade_serie=unidade_serie,
                pontos=tuple(pontos),
                confianca_minima=confianca_minima,
                revisao_humana=precisa_revisao,
            )
        )

    series.sort(key=lambda s: s.serie_id)
    return ResultadoSeries(tuple(series), tuple(pendencias))
