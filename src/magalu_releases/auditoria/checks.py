"""Auditoria automática do resultado, antes de qualquer alegação de conclusão.

Toda verificação vira uma linha — inclusive as que passaram. Uma auditoria que
só aparece quando falha não prova que rodou, e é exatamente essa prova que
sustenta a confiança na planilha.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from magalu_releases.models import VerificacaoAuditoria
from magalu_releases.vocabularios import (
    Confianca,
    ResultadoCheck,
    Severidade,
    TipoDocumento,
    TipoValor,
)

# --- Varredura de linguagem -------------------------------------------------
#
# O desafio aqui é distinguir a métrica legítima ("vendas totais", "venda de
# mercadorias") do conselho proibido ("vender a ação"). Por isso os padrões
# exigem o objeto do investimento — ação, papel, posição, ativo — e não apenas o
# verbo.

_OBJETO_INVESTIMENTO = r"(?:a[çc][õo]es?|papel|pap[ée]is|posi[çc][ãa]o|ativo|mglu\d?|ticker)"

_PADROES_RECOMENDACAO = (
    re.compile(rf"recomenda\w*\b[^.]{{0,60}}\b(?:compra|venda|manuten[çc][ãa]o|{_OBJETO_INVESTIMENTO})",
               re.IGNORECASE),
    re.compile(rf"\b(?:compr|vend)\w*\b[^.]{{0,40}}\b{_OBJETO_INVESTIMENTO}", re.IGNORECASE),
    re.compile(rf"\b{_OBJETO_INVESTIMENTO}\b[^.]{{0,40}}\b(?:compr|vend)\w*", re.IGNORECASE),
    re.compile(rf"\bmanter\b[^.]{{0,40}}\b{_OBJETO_INVESTIMENTO}", re.IGNORECASE),
    re.compile(r"\b(?:deve|deveria|vale a pena)\b[^.]{0,40}\b(?:compr|vend)\w*", re.IGNORECASE),
    re.compile(r"\b(?:sugerimos|aconselhamos|indicamos)\b[^.]{0,60}\b(?:compr|vend|manter)\w*",
               re.IGNORECASE),
)

_PADROES_PROMOCIONAIS = (
    r"s[óo]lid[oa]s?",
    r"robust[oa]s?",
    r"consistente(?:s|mente)?",
    r"expressiv[oa]s?",
    r"favor[áa]ve(?:l|is)",
    r"impressionante(?:s)?",
    r"excelente(?:s)?",
    r"not[áa]ve(?:l|is)",
    r"extraordin[áa]ri[oa]s?",
    r"excepcional(?:is|mente)?",
    r"vigoros[oa]s?",
    r"resiliente(?:s)?",
)
_PROMOCIONAL = re.compile(r"\b(" + "|".join(_PADROES_PROMOCIONAIS) + r")\b", re.IGNORECASE)


def varrer_linguagem_recomendacao(texto: str | None) -> tuple[str, ...]:
    """Trechos que um leitor poderia entender como conselho de investimento."""
    if not texto:
        return ()
    achados = []
    for padrao in _PADROES_RECOMENDACAO:
        achados.extend(m.group(0).strip() for m in padrao.finditer(texto))
    return tuple(dict.fromkeys(achados))


def varrer_linguagem_promocional(texto: str | None) -> tuple[str, ...]:
    """Adjetivação avaliativa: descreve um julgamento, não um número."""
    if not texto:
        return ()
    return tuple(dict.fromkeys(m.group(0) for m in _PROMOCIONAL.finditer(texto)))


# --- Relatório --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RelatorioAuditoria:
    verificacoes: tuple[VerificacaoAuditoria, ...]

    @property
    def falhas_altas(self) -> tuple[VerificacaoAuditoria, ...]:
        return tuple(
            v
            for v in self.verificacoes
            if v.resultado is ResultadoCheck.FAIL and v.severidade is Severidade.ALTA
        )

    @property
    def aprovado(self) -> bool:
        """Falha de severidade alta impede apresentar a entrega como concluída."""
        return not self.falhas_altas

    def resumo_por_resultado(self) -> dict[str, int]:
        contagem = {r.value: 0 for r in ResultadoCheck}
        for v in self.verificacoes:
            contagem[v.resultado.value] += 1
        return contagem


def _check(check_id, descricao, esperado, obtido, ok, severidade, detalhe="", alerta=False):
    if ok:
        resultado = ResultadoCheck.PASS
    else:
        resultado = ResultadoCheck.ALERTA if alerta else ResultadoCheck.FAIL
    return VerificacaoAuditoria(
        check_id=check_id,
        descricao=descricao,
        esperado=str(esperado),
        obtido=str(obtido),
        resultado=resultado,
        severidade=severidade,
        detalhe=detalhe,
    )


def auditar(
    *,
    n_pedido: int,
    documentos,
    fatos,
    series,
    variacoes,
    pendencias,
    resumo_texto: str | None = None,
    periodos=(),
) -> RelatorioAuditoria:
    """Roda o checklist completo e devolve o relatório."""
    documentos = list(documentos)
    fatos = list(fatos)
    series = list(series)
    variacoes = list(variacoes)
    pendencias = list(pendencias)
    periodos = tuple(periodos)

    v: list[VerificacaoAuditoria] = []

    # --- Escopo e seleção ---
    v.append(
        _check(
            "sel_quantidade",
            "Quantidade de documentos analisados igual a N pedido",
            n_pedido,
            len(documentos),
            len(documentos) == n_pedido,
            Severidade.MEDIA,
            "" if len(documentos) == n_pedido else "diferença precisa constar do Resumo",
            alerta=len(documentos) < n_pedido,
        )
    )

    nao_releases = [d for d in documentos if d.tipo is not TipoDocumento.RELEASE_RESULTADOS]
    v.append(
        _check(
            "sel_tipo",
            "Todo documento analisado é release de resultados",
            "0 documentos de outro tipo",
            f"{len(nao_releases)} de outro tipo",
            not nao_releases,
            Severidade.ALTA,
            ", ".join(d.documento_id for d in nao_releases),
        )
    )

    canonicos = [d.periodo.canonico for d in documentos if d.periodo]
    duplicados = sorted({c for c in canonicos if canonicos.count(c) > 1})
    v.append(
        _check(
            "sel_periodos_unicos",
            "Nenhum período fiscal duplicado entre os documentos",
            "0 duplicatas",
            f"{len(duplicados)} duplicata(s)",
            not duplicados,
            Severidade.ALTA,
            ", ".join(duplicados),
        )
    )

    v.append(
        _check(
            "sel_ordenacao",
            "Períodos em ordem cronológica crescente",
            "ordem crescente",
            "crescente" if canonicos == sorted(canonicos) else "fora de ordem",
            canonicos == sorted(canonicos),
            Severidade.ALTA,
        )
    )

    sem_periodo = [d for d in documentos if d.periodo is None]
    v.append(
        _check(
            "sel_periodo_origem",
            "Todo documento analisado tem período fiscal determinado",
            "0 sem período",
            f"{len(sem_periodo)} sem período",
            not sem_periodo,
            Severidade.ALTA,
            ", ".join(d.documento_id for d in sem_periodo),
        )
    )

    # --- Integridade da evidência ---
    sem_evidencia = [
        f for f in fatos if not f.documento_id or not f.trecho_fonte or f.pagina < 1
    ]
    v.append(
        _check(
            "evi_obrigatoria",
            "Todo fato tem documento, página e trecho-fonte",
            "0 fatos sem evidência",
            f"{len(sem_evidencia)} sem evidência",
            not sem_evidencia,
            Severidade.ALTA,
            ", ".join(f.fato_id for f in sem_evidencia[:10]),
        )
    )

    trecho_nao_contem = [f for f in fatos if f.valor_original.strip() not in f.trecho_fonte]
    v.append(
        _check(
            "evi_contem_valor",
            "trecho_fonte contém o valor_original",
            "0 divergências",
            f"{len(trecho_nao_contem)} divergência(s)",
            not trecho_nao_contem,
            Severidade.ALTA,
            ", ".join(f.fato_id for f in trecho_nao_contem[:10]),
        )
    )

    ids_documentos = {d.documento_id for d in documentos}
    orfaos = [f for f in fatos if f.documento_id not in ids_documentos]
    v.append(
        _check(
            "evi_documento_existe",
            "Todo documento citado por um fato existe na aba Documentos",
            "0 referências órfãs",
            f"{len(orfaos)} órfã(s)",
            not orfaos,
            Severidade.ALTA,
            ", ".join(f.fato_id for f in orfaos[:10]),
        )
    )

    ids_fatos = {f.fato_id for f in fatos}
    pontos_orfaos = [
        (s.serie_id, p.periodo_canonico)
        for s in series
        for p in s.pontos
        if p.fato_id and p.fato_id not in ids_fatos
    ]
    v.append(
        _check(
            "evi_rastro_comparativo",
            "Toda posição preenchida do Comparativo resolve para um fato conhecido",
            "0 pontos sem fato",
            f"{len(pontos_orfaos)} sem fato",
            not pontos_orfaos,
            Severidade.ALTA,
            "; ".join(f"{s} em {p}" for s, p in pontos_orfaos[:10]),
        )
    )

    # --- Valores e unidades ---
    zero_indevido = [
        f
        for f in fatos
        if f.valor_normalizado == 0.0 and f.motivo and "ausência" in (f.motivo or "")
    ]
    v.append(
        _check(
            "val_null_nao_zero",
            "Nenhuma ausência gravada como zero",
            "0 ocorrências",
            f"{len(zero_indevido)} ocorrência(s)",
            not zero_indevido,
            Severidade.ALTA,
            ", ".join(f.fato_id for f in zero_indevido[:10]),
        )
    )

    incoerentes = [f for f in fatos if f.unidade is None and f.valor_normalizado is not None]
    v.append(
        _check(
            "val_null_coerente",
            "valor_normalizado é nulo sempre que a unidade é nula",
            "0 incoerências",
            f"{len(incoerentes)} incoerência(s)",
            not incoerentes,
            Severidade.ALTA,
            ", ".join(f.fato_id for f in incoerentes[:10]),
        )
    )

    series_sem_unidade = [
        s for s in series if s.unidade_serie is None and any(p.fato_id for p in s.pontos)
    ]
    v.append(
        _check(
            "val_unidade_serie",
            "Cada série tem unidade única e coerente",
            "0 séries sem unidade definida",
            f"{len(series_sem_unidade)} sem unidade",
            not series_sem_unidade,
            Severidade.MEDIA,
            ", ".join(s.serie_id for s in series_sem_unidade[:10]),
            alerta=True,
        )
    )

    tipos_por_serie = {s.serie_id: s.tipo_valor for s in series}
    pp_errado = [
        x
        for x in variacoes
        if (
            tipos_por_serie.get(x.serie_id) is TipoValor.PERCENTUAL
            and x.variacao_pct is not None
        )
        or (
            tipos_por_serie.get(x.serie_id) is not TipoValor.PERCENTUAL
            and x.variacao_pp is not None
        )
    ]
    v.append(
        _check(
            "val_pp_vs_pct",
            "variacao_pp só em séries percentuais; variacao_pct nunca nelas",
            "0 trocas",
            f"{len(pp_errado)} troca(s)",
            not pp_errado,
            Severidade.ALTA,
            "; ".join(f"{x.serie_id} {x.periodo_de}->{x.periodo_para}" for x in pp_errado[:10]),
        )
    )

    # --- Comparação ---
    posicoes_erradas = [s for s in series if periodos and len(s.pontos) != len(periodos)]
    v.append(
        _check(
            "cmp_n_posicoes",
            "Toda série tem exatamente N posições, sem deslocamento",
            f"{len(periodos)} posições",
            f"{len(posicoes_erradas)} série(s) fora do padrão",
            not posicoes_erradas,
            Severidade.ALTA,
            ", ".join(s.serie_id for s in posicoes_erradas[:10]),
        )
    )

    ordem_errada = [
        s for s in series if [p.periodo_canonico for p in s.pontos] != sorted(
            [p.periodo_canonico for p in s.pontos]
        )
    ]
    v.append(
        _check(
            "cmp_ordem_series",
            "Posições de cada série em ordem cronológica crescente",
            "0 séries fora de ordem",
            f"{len(ordem_errada)} fora de ordem",
            not ordem_errada,
            Severidade.ALTA,
            ", ".join(s.serie_id for s in ordem_errada[:10]),
        )
    )

    confianca_baixa = {s.serie_id for s in series if s.confianca_minima is Confianca.BAIXA}
    calculada_com_baixa = [
        x for x in variacoes if x.calculada and x.serie_id in confianca_baixa
    ]
    v.append(
        _check(
            "cmp_confianca_baixa",
            "Nenhuma variação calculada sobre ponta de confiança baixa",
            "0 variações",
            f"{len(calculada_com_baixa)} variação(ões)",
            not calculada_com_baixa,
            Severidade.ALTA,
            "; ".join(x.serie_id for x in calculada_com_baixa[:10]),
        )
    )

    sem_base = [x for x in variacoes if x.base_comparacao is None]
    v.append(
        _check(
            "cmp_base_declarada",
            "Toda variação declara a base de comparação",
            "0 sem base",
            f"{len(sem_base)} sem base",
            not sem_base,
            Severidade.ALTA,
            "; ".join(f"{x.serie_id} {x.periodo_de}->{x.periodo_para}" for x in sem_base[:10]),
        )
    )

    texto_com_variacao = [
        x
        for x in variacoes
        if tipos_por_serie.get(x.serie_id) is TipoValor.TEXTO
        and (x.variacao_abs is not None or x.variacao_pct is not None)
    ]
    v.append(
        _check(
            "cmp_texto",
            "Séries textuais não têm variação numérica",
            "0 ocorrências",
            f"{len(texto_com_variacao)} ocorrência(s)",
            not texto_com_variacao,
            Severidade.ALTA,
        )
    )

    # --- Pendências e linguagem ---
    flags_incoerentes = [f for f in fatos if bool(f.flags) != f.revisao_humana]
    v.append(
        _check(
            "pen_flags_coerentes",
            "revisao_humana espelha a presença de flags",
            "0 incoerências",
            f"{len(flags_incoerentes)} incoerência(s)",
            not flags_incoerentes,
            Severidade.ALTA,
            ", ".join(f.fato_id for f in flags_incoerentes[:10]),
        )
    )

    precisam_revisao = [f for f in fatos if f.revisao_humana]
    v.append(
        _check(
            "pen_visivel",
            "Fatos marcados para revisão têm pendência registrada",
            "toda marcação com pendência",
            f"{len(precisam_revisao)} fato(s) marcado(s), {len(pendencias)} pendência(s)",
            not precisam_revisao or bool(pendencias),
            Severidade.MEDIA,
            alerta=True,
        )
    )

    recomendacoes = varrer_linguagem_recomendacao(resumo_texto)
    v.append(
        _check(
            "lng_sem_recomendacao",
            "Resumo sem linguagem de recomendação de investimento",
            "0 trechos",
            f"{len(recomendacoes)} trecho(s)",
            not recomendacoes,
            Severidade.ALTA,
            " | ".join(recomendacoes[:5]),
        )
    )

    promocionais = varrer_linguagem_promocional(resumo_texto)
    v.append(
        _check(
            "lng_sem_promocional",
            "Resumo sem adjetivação avaliativa ou promocional",
            "0 termos",
            f"{len(promocionais)} termo(s)",
            not promocionais,
            Severidade.MEDIA,
            " | ".join(promocionais[:8]),
            alerta=True,
        )
    )

    return RelatorioAuditoria(tuple(v))
