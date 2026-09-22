"""Normalização numérica no formato brasileiro.

Nos releases o separador de milhar é o ponto e o decimal é a vírgula. Aplicar a
convenção anglófona a `1.234,5` produz `1.234` — erro de fator mil cujo resultado
continua parecendo plausível numa planilha. Este módulo existe para que essa
conversão aconteça num só lugar, com teste denso.

Regra que atravessa tudo: na dúvida, `None` com motivo. Um número certo em
unidade errada é muito pior que um número ausente.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MARCADORES_AUSENCIA = frozenset(
    {"", "-", "--", "---", "—", "–", "n.a.", "na", "n/a", "n.d.", "nd", "n/d", "s.d."}
)

# Tokens de unidade removidos antes de validar o que sobrou como número.
_TOKENS_UNIDADE = re.compile(
    r"(r\$|us\$|%|p\.?\s?p\.?|\bmilh(?:ão|ões|ao|oes)\b|\bbilh(?:ão|ões|ao|oes)\b"
    r"|\bmil\b|\bmm\b|\bmi\b|\bbi\b)",
    re.IGNORECASE,
)

# Depois da limpeza, só estas duas formas são aceitas como número brasileiro.
# `\.\d{3}` exige grupos de exatamente três dígitos, o que rejeita "9.9"
# (que seria um decimal anglófono disfarçado).
_NUMERO_BR = re.compile(r"^(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)$")

_ESCALAS_MONETARIAS = (
    (re.compile(r"bilh(?:ão|ões|ao|oes)|\bbi\b", re.IGNORECASE), "R$ bilhões"),
    (re.compile(r"milh(?:ão|ões|ao|oes)|\bmi\b|\bmm\b", re.IGNORECASE), "R$ milhões"),
    (re.compile(r"\bmil\b", re.IGNORECASE), "R$ mil"),
)

_PONTO_PERCENTUAL = re.compile(r"p\.?\s?p\.?", re.IGNORECASE)
_MOEDA = re.compile(r"r\$", re.IGNORECASE)

# "Prejuízo" e "queda" com número positivo significam valor negativo. Perder isso
# transforma prejuízo em lucro.
ROTULOS_NEGATIVOS = re.compile(r"preju[íi]zo|queda|redu[çc][ãa]o|perda", re.IGNORECASE)

# Fatores para unificar escala dentro de uma série. Só monetárias convertem:
# "lojas" e "%" não têm escala, e forçar conversão inventaria significado.
FATORES_MONETARIOS = {
    "R$ mil": 1e3,
    "R$ milhões": 1e6,
    "R$ bilhões": 1e9,
}


class EscalaIncompativel(Exception):
    """As unidades não pertencem à mesma família e não podem ser convertidas."""


def converter_escala(valor: float, de: str, para: str) -> float:
    """Converte entre escalas monetárias, preservando o significado do número.

    Existe porque uma série pode trazer a tabela em milhares num release e em
    milhões no seguinte; comparar sem unificar produz um salto de fator mil que
    parece um resultado extraordinário.
    """
    if de == para:
        return valor
    if de not in FATORES_MONETARIOS or para not in FATORES_MONETARIOS:
        raise EscalaIncompativel(
            f"não há conversão definida entre {de!r} e {para!r}: "
            "só escalas monetárias são convertíveis"
        )
    return valor * (FATORES_MONETARIOS[de] / FATORES_MONETARIOS[para])


@dataclass(frozen=True, slots=True)
class ValorInterpretado:
    """O original é preservado literalmente; o normalizado pode legitimamente ser None."""

    original: str
    normalizado: float | None
    unidade: str | None
    motivo: str | None


def _sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def eh_marcador_ausencia(texto: str | None) -> bool:
    """`-`, `—`, `n.a.` e afins significam ausência — nunca zero."""
    if texto is None:
        return True
    bruto = texto.strip()
    if bruto in MARCADORES_AUSENCIA:
        return True
    return _sem_acentos(bruto).lower() in MARCADORES_AUSENCIA


def normalizar_numero_ptbr(texto: str | None) -> float | None:
    """Converte um número escrito à brasileira. Devolve None se não for um número.

    Não inventa interpretação: qualquer coisa que não case exatamente com o
    formato esperado vira None, para que o chamador registre a pendência.
    """
    if texto is None:
        return None

    s = texto.strip()
    if not s:
        return None

    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo = True
        s = s[1:-1].strip()

    s = _TOKENS_UNIDADE.sub(" ", s).strip()

    if s.startswith("-"):
        negativo = True
        s = s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()

    s = s.replace("\xa0", "").replace(" ", "")
    if not _NUMERO_BR.match(s):
        return None

    valor = float(s.replace(".", "").replace(",", "."))
    return -valor if negativo else valor


def detectar_unidade(texto: str) -> str | None:
    """Extrai a unidade do próprio texto do valor, quando ela estiver ali.

    Percentual e ponto percentual são autoevidentes; escala monetária quase nunca
    é — ela costuma morar no cabeçalho da tabela, longe do número.
    """
    if _PONTO_PERCENTUAL.search(texto):
        return "p.p."
    if "%" in texto:
        return "%"

    tem_moeda = bool(_MOEDA.search(texto))
    for padrao, unidade in _ESCALAS_MONETARIAS:
        if padrao.search(texto):
            return unidade if tem_moeda else None
    return None


def interpretar_valor(
    original: str,
    *,
    unidade_contexto: str | None = None,
    rotulo: str | None = None,
) -> ValorInterpretado:
    """Interpreta um valor tal como aparece no documento.

    `unidade_contexto` é a unidade lida do cabeçalho da tabela ou da nota. Sem ela,
    um valor monetário sem escala explícita permanece `None`: `R$ 9.856,4` pode ser
    milhares ou milhões, e os dois parecem razoáveis.
    """
    if eh_marcador_ausencia(original):
        return ValorInterpretado(
            original=original,
            normalizado=None,
            unidade=None,
            motivo="marcador de ausência no documento",
        )

    unidade = detectar_unidade(original) or unidade_contexto

    if unidade is None:
        motivo = (
            "escala monetária não determinada no documento"
            if _MOEDA.search(original)
            else "unidade não determinada para o valor"
        )
        return ValorInterpretado(
            original=original, normalizado=None, unidade=None, motivo=motivo
        )

    numero = normalizar_numero_ptbr(original)
    if numero is None:
        return ValorInterpretado(
            original=original,
            normalizado=None,
            unidade=unidade,
            motivo="não foi possível interpretar o texto como número brasileiro",
        )

    if rotulo and ROTULOS_NEGATIVOS.search(rotulo) and numero > 0:
        numero = -numero

    return ValorInterpretado(
        original=original, normalizado=numero, unidade=unidade, motivo=None
    )
