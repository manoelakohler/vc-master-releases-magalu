"""Modelos do contrato de dados e suas invariantes.

As invariantes ficam em `validar_fato` — e não no construtor — porque o portão
semântico precisa relatar **todas** as violações de um arquivo de fatos de uma
vez, com mensagem acionável, em vez de parar na primeira.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from magalu_releases.periodos import PeriodoFiscal
from magalu_releases.vocabularios import (
    Base,
    BaseComparacao,
    Confianca,
    Gatilho,
    Periodicidade,
    ResultadoCheck,
    Segmento,
    Severidade,
    TipoDocumento,
    TipoValor,
)

ChaveSerie = tuple[str, Segmento, Base, Periodicidade, TipoValor]


@dataclass(frozen=True, slots=True)
class Fato:
    """Um valor extraído de um documento, com tudo que o torna verificável."""

    fato_id: str
    metrica_id: str
    metrica_rotulo: str
    segmento: Segmento
    base: Base
    periodicidade: Periodicidade
    tipo_valor: TipoValor
    periodo: PeriodoFiscal
    valor_original: str
    valor_normalizado: float | None
    unidade: str | None
    documento_id: str
    pagina: int
    trecho_fonte: str
    confianca: Confianca
    flags: tuple[Gatilho, ...] = ()
    revisao_humana: bool = False
    motivo: str | None = None


@dataclass(frozen=True, slots=True)
class PontoSerie:
    periodo_canonico: str
    fato_id: str | None
    valor_normalizado: float | None
    valor_original: str | None


@dataclass(frozen=True, slots=True)
class Serie:
    serie_id: str
    metrica_id: str
    metrica_rotulo: str
    segmento: Segmento
    base: Base
    periodicidade: Periodicidade
    tipo_valor: TipoValor
    unidade_serie: str | None
    pontos: tuple[PontoSerie, ...]
    confianca_minima: Confianca | None
    revisao_humana: bool = False


@dataclass(frozen=True, slots=True)
class Variacao:
    serie_id: str
    periodo_de: str
    periodo_para: str
    base_comparacao: BaseComparacao
    variacao_abs: float | None = None
    variacao_pct: float | None = None
    variacao_pp: float | None = None
    calculada: bool = False
    motivo_nao_calculada: str | None = None


@dataclass(frozen=True, slots=True)
class Documento:
    documento_id: str
    titulo: str
    tipo: TipoDocumento
    periodo: PeriodoFiscal | None
    url_origem: str
    data_publicacao: str | None = None
    arquivo_local: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    paginas: int | None = None
    textual: bool | None = None
    baixado_em: str | None = None
    # Nome que o servidor deu ao arquivo no Content-Disposition. Na Central
    # o link é opaco, então esta é a única declaração independente de que o
    # PDF baixado é o release daquele período.
    nome_servidor: str | None = None
    motivo_descarte: str | None = None


@dataclass(frozen=True, slots=True)
class Pendencia:
    pendencia_id: str
    tipo: Gatilho
    severidade: Severidade
    descricao: str
    referencias: tuple[str, ...] = ()
    valores_conflitantes: tuple[str, ...] = ()
    acao_sugerida: str = ""
    status: str = "aberta"


@dataclass(frozen=True, slots=True)
class VerificacaoAuditoria:
    check_id: str
    descricao: str
    esperado: str
    obtido: str
    resultado: ResultadoCheck
    severidade: Severidade
    detalhe: str = ""


@dataclass(frozen=True, slots=True)
class PaginaTexto:
    documento_id: str
    pagina: int
    texto: str
    caracteres: int
    tabela_suspeita: bool = False
    observacao: str | None = None


@dataclass(frozen=True, slots=True)
class Execucao:
    run_id: str
    n_pedido: int
    n_obtido: int
    iniciada_em: str
    fonte: str
    periodos: tuple[str, ...] = field(default_factory=tuple)


def chave_serie(fato: Fato) -> ChaveSerie:
    """A identidade de uma série é a tupla completa.

    É o que impede lucro ajustado de virar lucro reportado, trimestre de virar
    acumulado e e-commerce de virar consolidado — misturas que produzem uma série
    coerente na aparência e falsa no conteúdo.
    """
    return (
        fato.metrica_id,
        fato.segmento,
        fato.base,
        fato.periodicidade,
        fato.tipo_valor,
    )


def validar_fato(fato: Fato) -> tuple[str, ...]:
    """Devolve todas as violações de invariante do fato. Tupla vazia = válido."""
    violacoes: list[str] = []

    if not fato.fato_id.strip():
        violacoes.append("fato_id é obrigatório")
    if not fato.metrica_id.strip():
        violacoes.append("metrica_id é obrigatório")

    # Evidência: sem os três, não é fato — é suposição.
    if not fato.documento_id.strip():
        violacoes.append("documento_id é obrigatório: evidência sem documento não sustenta valor")
    if not isinstance(fato.pagina, int) or fato.pagina < 1:
        violacoes.append(f"pagina deve ser inteiro >= 1, recebido {fato.pagina!r}")
    if not fato.trecho_fonte.strip():
        violacoes.append("trecho_fonte é obrigatório: sem ele a evidência não é verificável")

    if not fato.valor_original.strip():
        violacoes.append("valor_original nunca é vazio: sem texto de origem não há fato")
    elif fato.trecho_fonte.strip() and fato.valor_original.strip() not in fato.trecho_fonte:
        violacoes.append(
            f"trecho_fonte não contém valor_original {fato.valor_original!r}: "
            "a evidência não sustenta o valor"
        )

    # Unidade ausente implica normalizado ausente: um número certo em unidade
    # errada é muito pior que um número ausente.
    if fato.unidade is None and fato.valor_normalizado is not None:
        violacoes.append(
            "unidade ausente exige valor_normalizado nulo "
            f"(recebido {fato.valor_normalizado!r})"
        )

    tem_flags = bool(fato.flags)
    if tem_flags != fato.revisao_humana:
        violacoes.append(
            f"revisao_humana ({fato.revisao_humana}) precisa espelhar a presença de flags "
            f"({list(fato.flags)})"
        )

    if fato.confianca is Confianca.BAIXA and not fato.revisao_humana:
        violacoes.append("confianca baixa implica revisao_humana e pendência registrada")

    if fato.base is Base.INDEFINIDO and not fato.revisao_humana:
        violacoes.append(
            "base indefinida exige revisão humana: não se escolhe entre ajustado e "
            "reportado por conta própria"
        )

    if fato.tipo_valor is TipoValor.PERCENTUAL and fato.unidade == "p.p.":
        violacoes.append("tipo_valor percentual com unidade p.p.: nível e variação não se misturam")

    return tuple(violacoes)
