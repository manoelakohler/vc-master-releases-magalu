"""Esqueleto factual do resumo executivo e validação da sua linguagem.

O texto final é redigido na fase de análise, guiada pela skill — julgamento não
vira código. O que este módulo faz é determinístico: monta o esqueleto com os
números já apurados, na estrutura de seis partes, e recusa linguagem que soe
como recomendação ou avaliação.

O esqueleto descreve direção e magnitude do que está impresso. Quando um dado
está ausente, ele **diz que está ausente**, em vez de contornar com uma frase que
dá impressão de cobertura completa.
"""

from __future__ import annotations

from magalu_releases.auditoria.checks import (
    varrer_linguagem_promocional,
    varrer_linguagem_recomendacao,
)

SECOES = (
    "1. Escopo analisado",
    "2. O que os números mostram",
    "3. Variações relevantes",
    "4. Conflitos e ambiguidades",
    "5. Lacunas",
    "6. Itens de revisão humana",
)


def _numero(valor: float | None) -> str:
    if valor is None:
        return "ausente"
    inteiro = abs(valor - round(valor)) < 1e-9
    texto = f"{valor:,.0f}" if inteiro else f"{valor:,.1f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _valor_enum(valor):
    return valor.value if hasattr(valor, "value") else valor


def contar_periodos_analisados(periodos, documentos) -> int:
    """Quantos períodos foram de fato analisados, descontando os descartados.

    Um PDF não textual continua listado na aba Documentos com o motivo, mas não
    foi lido. Contá-lo faz o Resumo alegar cobertura que a auditoria nega — e
    duas células do mesmo arquivo em contradição é o pior tipo de erro aqui.
    """
    periodos = tuple(periodos)
    descartados = {
        d.periodo.canonico for d in documentos if d.periodo and d.motivo_descarte
    }
    analisados = {
        d.periodo.canonico for d in documentos if d.periodo and not d.motivo_descarte
    }
    return len([c for c in periodos if c not in descartados or c in analisados])


def montar_esqueleto(
    *, n_pedido, periodos, rotulos, series, variacoes, pendencias, documentos
) -> str:
    """Monta o resumo factual a partir do que foi apurado."""
    periodos = tuple(periodos)
    n_obtido = contar_periodos_analisados(periodos, documentos)
    linhas: list[str] = []

    linhas.append(SECOES[0])
    linhas.append(f"- Releases pedidos: {n_pedido}. Releases analisados: {n_obtido}.")
    if n_obtido < n_pedido:
        linhas.append(
            f"- Foram pedidos {n_pedido} releases e localizados {n_obtido}; "
            "a diferença consta da aba Auditoria."
        )
    linhas.append(
        "- Períodos, em ordem cronológica crescente: "
        + ", ".join(rotulos.get(c, c) for c in periodos)
        + "."
    )
    linhas.append(f"- Documentos utilizados: {len(documentos)}.")
    linhas.append("")

    linhas.append(SECOES[1])
    if not series:
        linhas.append("- Nenhuma série foi construída nesta execução.")
    for serie in series:
        unidade = serie.unidade_serie or "unidade não determinada"
        partes = []
        for ponto in serie.pontos:
            rotulo = rotulos.get(ponto.periodo_canonico, ponto.periodo_canonico)
            partes.append(f"{rotulo}: {_numero(ponto.valor_normalizado)}")
        linhas.append(
            f"- {serie.metrica_rotulo} ({_valor_enum(serie.segmento)}, "
            f"{_valor_enum(serie.base)}, {_valor_enum(serie.periodicidade)}) "
            f"em {unidade} — " + "; ".join(partes) + "."
        )
    linhas.append("")

    linhas.append(SECOES[2])
    calculadas = [v for v in variacoes if v.calculada]
    suprimidas = [v for v in variacoes if not v.calculada]
    if not variacoes:
        linhas.append("- Nenhuma variação foi calculada nesta execução.")
    for v in calculadas:
        de = rotulos.get(v.periodo_de, v.periodo_de)
        para = rotulos.get(v.periodo_para, v.periodo_para)
        if v.variacao_pp is not None:
            medida = f"{_numero(v.variacao_pp)} p.p."
        elif v.variacao_pct is not None:
            medida = f"{_numero(v.variacao_pct)}%"
        else:
            medida = _numero(v.variacao_abs)
        linhas.append(
            f"- {v.serie_id}: de {de} para {para}, variação de {medida} "
            f"(base: {_valor_enum(v.base_comparacao)})."
        )
    for v in suprimidas:
        de = rotulos.get(v.periodo_de, v.periodo_de)
        para = rotulos.get(v.periodo_para, v.periodo_para)
        linhas.append(
            f"- {v.serie_id}: variação de {de} para {para} não calculada — "
            f"{v.motivo_nao_calculada}."
        )
    linhas.append("")

    conflitos = [p for p in pendencias if _valor_enum(p.tipo) == "conflito"]
    linhas.append(SECOES[3])
    if not conflitos:
        linhas.append("- Nenhum conflito entre documentos foi registrado.")
    for p in conflitos:
        linhas.append(f"- {p.pendencia_id}: {p.descricao}.")
    linhas.append("")

    linhas.append(SECOES[4])
    lacunas = [
        (serie, ponto)
        for serie in series
        for ponto in serie.pontos
        if ponto.valor_normalizado is None
    ]
    if not lacunas:
        linhas.append("- Nenhuma lacuna: todas as posições das séries foram preenchidas.")
    for serie, ponto in lacunas:
        rotulo = rotulos.get(ponto.periodo_canonico, ponto.periodo_canonico)
        linhas.append(
            f"- {serie.metrica_rotulo} em {rotulo}: valor ausente (null), "
            "não reportado no documento correspondente."
        )
    linhas.append("")

    linhas.append(SECOES[5])
    revisoes = [p for p in pendencias if _valor_enum(p.tipo) != "conflito"]
    if not revisoes:
        linhas.append("- Nenhum item adicional marcado para revisão humana.")
    for p in revisoes:
        linhas.append(
            f"- {p.pendencia_id} ({_valor_enum(p.severidade)}): {p.descricao}. "
            f"Ação: {p.acao_sugerida or 'conferir no documento de origem'}."
        )

    return "\n".join(linhas)


def validar_resumo(texto: str | None) -> tuple[str, ...]:
    """Recusa linguagem de recomendação e adjetivação avaliativa."""
    problemas: list[str] = []
    for trecho in varrer_linguagem_recomendacao(texto):
        problemas.append(f"linguagem de recomendação de investimento: {trecho!r}")
    for termo in varrer_linguagem_promocional(texto):
        problemas.append(f"adjetivação avaliativa: {termo!r}")
    return tuple(problemas)
