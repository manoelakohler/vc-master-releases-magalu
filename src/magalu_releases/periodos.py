"""Período fiscal: interpretação, forma canônica e ordenação.

O release do 4T é publicado no ano seguinte. Ordenar por data de publicação
coloca o 4T24 depois do 1T25 e o resultado continua parecendo uma lista
ordenada — por isso a ordenação é sempre pelo período fiscal.

Período que não pode ser determinado com segurança levanta exceção. Chutar aqui
contamina toda a comparação a jusante, de forma invisível.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from magalu_releases.vocabularios import Periodicidade


class PeriodoIndeterminado(Exception):
    """O texto não identifica um período fiscal de forma inequívoca."""


@dataclass(frozen=True, slots=True)
class PeriodoFiscal:
    ano: int
    trimestre: int | None
    periodicidade: Periodicidade
    canonico: str
    rotulo: str
    posicao: int = field(compare=False)

    @property
    def chave_ordenacao(self) -> tuple[int, int]:
        return (self.ano, self.posicao)

    def __lt__(self, outro: object) -> bool:
        if not isinstance(outro, PeriodoFiscal):
            return NotImplemented
        return self.chave_ordenacao < outro.chave_ordenacao

    def __le__(self, outro: object) -> bool:
        if not isinstance(outro, PeriodoFiscal):
            return NotImplemented
        return self.chave_ordenacao <= outro.chave_ordenacao

    def __gt__(self, outro: object) -> bool:
        if not isinstance(outro, PeriodoFiscal):
            return NotImplemented
        return self.chave_ordenacao > outro.chave_ordenacao

    def __ge__(self, outro: object) -> bool:
        if not isinstance(outro, PeriodoFiscal):
            return NotImplemented
        return self.chave_ordenacao >= outro.chave_ordenacao


_TRIMESTRE_T = re.compile(r"^([1-4])\s*T\s*(\d{4}|\d{2})$", re.IGNORECASE)
_TRIMESTRE_Q = re.compile(r"^([1-4])\s*Q\s*(\d{4}|\d{2})$", re.IGNORECASE)
_TRIMESTRE_Q_PREFIXO = re.compile(r"^Q\s*([1-4])[\s/-]+(\d{4}|\d{2})$", re.IGNORECASE)
_MESES = re.compile(r"^(\d{1,2})\s*M\s*(\d{4}|\d{2})$", re.IGNORECASE)
_SEMESTRE = re.compile(r"^([12])\s*S\s*(\d{4}|\d{2})$", re.IGNORECASE)
_ANO_ISOLADO = re.compile(r"^(?:exerc[íi]cio\s+de\s+)?(20\d{2})$", re.IGNORECASE)


def _ano_completo(bruto: str) -> int:
    """Dois dígitos são sempre 20XX neste domínio — não há release do século passado."""
    valor = int(bruto)
    return valor if valor >= 1000 else 2000 + valor


def interpretar_periodo(texto: str | None) -> PeriodoFiscal:
    """Interpreta a notação do documento. Levanta `PeriodoIndeterminado` se não der.

    Aceita `1T25`, `2T2025`, `2Q25`, `Q2 2025`, `9M25`, `1S25`, `12M25` e o ano
    isolado. `2S25` é recusado de propósito: semestre isolado não é a mesma coisa
    que acumulado, e assumir um dos dois seria chute.
    """
    if texto is None:
        raise PeriodoIndeterminado("texto ausente")

    bruto = texto.strip()
    if not bruto:
        raise PeriodoIndeterminado("texto vazio")

    if m := (_TRIMESTRE_T.match(bruto) or _TRIMESTRE_Q.match(bruto)):
        trimestre, ano = int(m.group(1)), _ano_completo(m.group(2))
        return _trimestral(ano, trimestre, bruto)

    if m := _TRIMESTRE_Q_PREFIXO.match(bruto):
        trimestre, ano = int(m.group(1)), _ano_completo(m.group(2))
        return _trimestral(ano, trimestre, bruto)

    if m := _MESES.match(bruto):
        meses, ano = int(m.group(1)), _ano_completo(m.group(2))
        if meses == 12:
            return PeriodoFiscal(ano, None, Periodicidade.ANUAL, f"{ano}-FY", bruto, 4)
        if meses in (3, 6, 9):
            return PeriodoFiscal(
                ano, None, Periodicidade.ACUMULADO, f"{ano}-{meses}M", bruto, meses // 3
            )
        raise PeriodoIndeterminado(f"acumulado de {meses} meses não é reconhecido: {bruto!r}")

    if m := _SEMESTRE.match(bruto):
        semestre, ano = int(m.group(1)), _ano_completo(m.group(2))
        if semestre == 1:
            return PeriodoFiscal(ano, None, Periodicidade.ACUMULADO, f"{ano}-6M", bruto, 2)
        raise PeriodoIndeterminado(
            f"{bruto!r}: segundo semestre isolado não equivale a acumulado"
        )

    if m := _ANO_ISOLADO.match(bruto):
        ano = int(m.group(1))
        return PeriodoFiscal(ano, None, Periodicidade.ANUAL, f"{ano}-FY", bruto, 4)

    raise PeriodoIndeterminado(f"não foi possível determinar o período em {bruto!r}")


def _trimestral(ano: int, trimestre: int, rotulo: str) -> PeriodoFiscal:
    return PeriodoFiscal(
        ano=ano,
        trimestre=trimestre,
        periodicidade=Periodicidade.TRIMESTRE,
        canonico=f"{ano}-Q{trimestre}",
        rotulo=rotulo,
        posicao=trimestre,
    )


def ordenar_periodos(periodos) -> list[PeriodoFiscal]:
    """Ordem cronológica crescente — a única usada em toda a saída."""
    return sorted(periodos, key=lambda p: p.chave_ordenacao)
