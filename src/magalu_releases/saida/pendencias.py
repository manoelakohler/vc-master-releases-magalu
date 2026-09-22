"""Consolidação das pendências vindas de todas as etapas.

Pendências chegam da seleção, da construção de séries e da própria análise. Aqui
elas viram uma lista única, numerada de forma estável e ordenada por severidade
— porque quem abre a aba precisa ver primeiro o que mais compromete o resultado.

Duplicata idêntica é removida: a mesma observação relatada por duas etapas é uma
observação, e repeti-la só dilui a lista.
"""

from __future__ import annotations

from dataclasses import replace

from magalu_releases.models import Pendencia
from magalu_releases.vocabularios import Gatilho, Severidade

_ORDEM_SEVERIDADE = {Severidade.ALTA: 0, Severidade.MEDIA: 1, Severidade.BAIXA: 2}


class PendenciaInvalida(Exception):
    """O registro lido não descreve uma pendência do vocabulário."""


def pendencia_de_dict(bruto: dict) -> Pendencia:
    """Reconstrói uma pendência gravada no manifesto da Fase A.

    A coleta detecta pendências que a Fase C precisa entregar — documento não
    classificado, período duplicado, lacuna trimestral. Entre as duas fases elas
    viajam como JSON, e sem esta volta a pendência existe no disco mas não na
    planilha: a execução termina parecendo limpa.
    """
    try:
        tipo = Gatilho(bruto["tipo"])
        severidade = Severidade(bruto["severidade"])
    except KeyError as exc:
        raise PendenciaInvalida(f"pendência sem o campo {exc}: {bruto!r}") from exc
    except ValueError as exc:
        raise PendenciaInvalida(f"valor fora do vocabulário em {bruto!r}: {exc}") from exc

    descricao = str(bruto.get("descricao", "")).strip()
    if not descricao:
        raise PendenciaInvalida(f"pendência sem descrição: {bruto!r}")

    return Pendencia(
        pendencia_id=str(bruto.get("pendencia_id", "")),
        tipo=tipo,
        severidade=severidade,
        descricao=descricao,
        referencias=tuple(bruto.get("referencias") or ()),
        valores_conflitantes=tuple(bruto.get("valores_conflitantes") or ()),
        acao_sugerida=str(bruto.get("acao_sugerida") or ""),
        status=str(bruto.get("status") or "aberta"),
    )


def consolidar_pendencias(*grupos) -> tuple[Pendencia, ...]:
    """Junta, deduplica, ordena por severidade e renumera."""
    vistas: dict[tuple, Pendencia] = {}
    for grupo in grupos:
        for pendencia in grupo or ():
            chave = (
                pendencia.tipo,
                pendencia.severidade,
                pendencia.descricao,
                pendencia.referencias,
                pendencia.valores_conflitantes,
            )
            vistas.setdefault(chave, pendencia)

    ordenadas = sorted(
        vistas.values(),
        key=lambda p: (_ORDEM_SEVERIDADE.get(p.severidade, 9), p.tipo.value, p.descricao),
    )
    return tuple(
        replace(p, pendencia_id=f"pen-{indice:04d}")
        for indice, p in enumerate(ordenadas, start=1)
    )
