"""O portão semântico.

Este módulo é o único caminho pelo qual valor semântico entra no pipeline. Tudo
que vem da leitura dos documentos — feita fora do código, guiada pela skill —
passa por aqui antes de virar série, planilha ou resumo.

Ele relata **todos** os problemas de uma vez, e não só o primeiro: corrigir um
arquivo de fatos descobrindo um erro por execução seria um jogo de tentativa e
erro, e o objetivo é que a correção seja um trabalho só.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from magalu_releases.models import Fato, validar_fato
from magalu_releases.periodos import PeriodoIndeterminado, interpretar_periodo
from magalu_releases.vocabularios import (
    Base,
    Confianca,
    Gatilho,
    Periodicidade,
    Segmento,
    TipoValor,
)

_CAMPOS_OBRIGATORIOS = (
    "fato_id",
    "metrica_id",
    "metrica_rotulo",
    "segmento",
    "base",
    "periodicidade",
    "tipo_valor",
    "periodo_rotulo",
    "valor_original",
    "documento_id",
    "pagina",
    "trecho_fonte",
    "confianca",
)

_ENUMS = {
    "segmento": Segmento,
    "base": Base,
    "periodicidade": Periodicidade,
    "tipo_valor": TipoValor,
    "confianca": Confianca,
}


class FatosInvalidos(Exception):
    """O arquivo de fatos não pôde ser lido ou viola o contrato."""


@dataclass(frozen=True, slots=True)
class ResultadoCarga:
    fatos: tuple[Fato, ...]
    problemas: tuple[str, ...]
    run_id: str | None = None


def _converter(bruto: dict, indice: int) -> tuple[Fato | None, list[str]]:
    etiqueta = f"[{indice}] {bruto.get('fato_id', 'sem fato_id')!r}"
    problemas: list[str] = []

    for campo in _CAMPOS_OBRIGATORIOS:
        if campo not in bruto or bruto[campo] in (None, ""):
            problemas.append(f"{etiqueta}: campo obrigatório ausente ou vazio: {campo}")

    valores: dict = {}
    for campo, enum in _ENUMS.items():
        cru = bruto.get(campo)
        try:
            valores[campo] = enum(cru)
        except ValueError:
            problemas.append(
                f"{etiqueta}: {campo}={cru!r} fora do vocabulário "
                f"({[e.value for e in enum]})"
            )

    flags = []
    for cru in bruto.get("flags") or []:
        try:
            flags.append(Gatilho(cru))
        except ValueError:
            problemas.append(f"{etiqueta}: flag {cru!r} não é um gatilho conhecido")

    periodo = None
    try:
        periodo = interpretar_periodo(bruto.get("periodo_rotulo"))
    except PeriodoIndeterminado as exc:
        problemas.append(f"{etiqueta}: período indeterminado ({exc})")

    if problemas:
        return None, problemas

    fato = Fato(
        fato_id=str(bruto["fato_id"]),
        metrica_id=str(bruto["metrica_id"]),
        metrica_rotulo=str(bruto["metrica_rotulo"]),
        segmento=valores["segmento"],
        base=valores["base"],
        periodicidade=valores["periodicidade"],
        tipo_valor=valores["tipo_valor"],
        periodo=periodo,
        valor_original=str(bruto["valor_original"]),
        valor_normalizado=(
            float(bruto["valor_normalizado"])
            if bruto.get("valor_normalizado") is not None
            else None
        ),
        unidade=bruto.get("unidade"),
        documento_id=str(bruto["documento_id"]),
        pagina=int(bruto["pagina"]) if str(bruto.get("pagina", "")).strip() else 0,
        trecho_fonte=str(bruto["trecho_fonte"]),
        confianca=valores["confianca"],
        flags=tuple(flags),
        revisao_humana=bool(bruto.get("revisao_humana", False)),
        motivo=bruto.get("motivo"),
    )

    return fato, [f"{etiqueta}: {v}" for v in validar_fato(fato)]


def carregar_fatos(caminho: Path | str, *, estrito: bool = True) -> ResultadoCarga:
    """Lê e valida o arquivo de fatos.

    Com `estrito=True` (padrão), qualquer violação impede a carga: é o portão
    fechando. Com `estrito=False`, devolve os problemas para que a etapa de
    validação possa listá-los ao usuário sem interromper.
    """
    origem = Path(caminho)
    if not origem.is_file():
        raise FatosInvalidos(f"arquivo de fatos não encontrado: {origem}")

    try:
        corpo = json.loads(origem.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FatosInvalidos(f"JSON inválido em {origem}: {exc}") from exc

    if not isinstance(corpo, dict) or "fatos" not in corpo:
        raise FatosInvalidos(f"{origem} não tem a chave 'fatos' no nível raiz")

    brutos = corpo["fatos"]
    if not isinstance(brutos, list):
        raise FatosInvalidos(f"{origem}: 'fatos' precisa ser uma lista")

    fatos: list[Fato] = []
    problemas: list[str] = []
    for indice, bruto in enumerate(brutos):
        if not isinstance(bruto, dict):
            problemas.append(f"[{indice}]: cada fato precisa ser um objeto JSON")
            continue
        fato, achados = _converter(bruto, indice)
        problemas.extend(achados)
        if fato is not None:
            fatos.append(fato)

    vistos: set[str] = set()
    for fato in fatos:
        if fato.fato_id in vistos:
            problemas.append(f"fato_id duplicado: {fato.fato_id!r}")
        vistos.add(fato.fato_id)

    if problemas and estrito:
        cabecalho = f"{len(problemas)} violação(ões) do contrato em {origem}:"
        raise FatosInvalidos("\n".join([cabecalho, *(f"  - {p}" for p in problemas)]))

    return ResultadoCarga(tuple(fatos), tuple(problemas), corpo.get("run_id"))


def serializar_fatos(fatos) -> list[dict]:
    """Converte fatos de volta para JSON, preservando o texto original intacto."""
    return [
        {
            "fato_id": f.fato_id,
            "metrica_id": f.metrica_id,
            "metrica_rotulo": f.metrica_rotulo,
            "segmento": f.segmento.value,
            "base": f.base.value,
            "periodicidade": f.periodicidade.value,
            "tipo_valor": f.tipo_valor.value,
            "periodo_rotulo": f.periodo.rotulo,
            "periodo_canonico": f.periodo.canonico,
            "valor_original": f.valor_original,
            "valor_normalizado": f.valor_normalizado,
            "unidade": f.unidade,
            "documento_id": f.documento_id,
            "pagina": f.pagina,
            "trecho_fonte": f.trecho_fonte,
            "confianca": f.confianca.value,
            "flags": [g.value for g in f.flags],
            "revisao_humana": f.revisao_humana,
            "motivo": f.motivo,
        }
        for f in fatos
    ]
