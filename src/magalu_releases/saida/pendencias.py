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
from magalu_releases.vocabularios import Severidade

_ORDEM_SEVERIDADE = {Severidade.ALTA: 0, Severidade.MEDIA: 1, Severidade.BAIXA: 2}


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
