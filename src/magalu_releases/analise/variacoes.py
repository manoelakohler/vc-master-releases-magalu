"""Cálculo das variações entre períodos consecutivos de uma série.

As regras de supressão são o conteúdo principal deste módulo. Não calcular é uma
decisão ativa: uma variação apoiada em base frágil aparece na planilha com a
mesma aparência de solidez de qualquer outra, e é justamente isso que a torna
perigosa.

Margens e percentuais variam em pontos percentuais. De 10% para 12% são 2 p.p.,
não "20%" — que é como o leitor entenderia uma variação percentual ali.
"""

from __future__ import annotations

from magalu_releases.models import Serie, Variacao
from magalu_releases.vocabularios import BaseComparacao, Confianca, TipoValor

_TOLERANCIA_ZERO = 1e-12


def calcular_variacoes(
    serie: Serie,
    *,
    base_comparacao: BaseComparacao = BaseComparacao.PERIODO_ANTERIOR,
) -> tuple[Variacao, ...]:
    """Uma variação por par consecutivo de posições da série."""
    resultados: list[Variacao] = []

    for anterior, atual in zip(serie.pontos, serie.pontos[1:]):
        molde = dict(
            serie_id=serie.serie_id,
            periodo_de=anterior.periodo_canonico,
            periodo_para=atual.periodo_canonico,
            base_comparacao=base_comparacao,
        )

        if serie.tipo_valor is TipoValor.TEXTO:
            resultados.append(
                Variacao(
                    **molde,
                    calculada=False,
                    motivo_nao_calculada="valores textuais comparam-se apenas qualitativamente",
                )
            )
            continue

        if serie.confianca_minima is Confianca.BAIXA:
            resultados.append(
                Variacao(
                    **molde,
                    calculada=False,
                    motivo_nao_calculada=(
                        "confiança baixa na série: a variação herdaria a fragilidade "
                        "sem deixar isso visível"
                    ),
                )
            )
            continue

        de, para = anterior.valor_normalizado, atual.valor_normalizado
        if de is None or para is None:
            ausente = anterior.periodo_canonico if de is None else atual.periodo_canonico
            resultados.append(
                Variacao(
                    **molde,
                    calculada=False,
                    motivo_nao_calculada=f"valor ausente em {ausente}",
                )
            )
            continue

        # Margens e percentuais: a diferença é em pontos percentuais.
        if serie.tipo_valor is TipoValor.PERCENTUAL:
            resultados.append(
                Variacao(**molde, variacao_pp=para - de, calculada=True)
            )
            continue

        variacao_abs = para - de

        if abs(de) <= _TOLERANCIA_ZERO:
            resultados.append(
                Variacao(
                    **molde,
                    variacao_abs=variacao_abs,
                    variacao_pct=None,
                    calculada=True,
                    motivo_nao_calculada=(
                        "variação percentual indefinida: o valor anterior é zero"
                    ),
                )
            )
            continue

        resultados.append(
            Variacao(
                **molde,
                variacao_abs=variacao_abs,
                variacao_pct=(variacao_abs / abs(de)) * 100.0,
                calculada=True,
            )
        )

    return tuple(resultados)
