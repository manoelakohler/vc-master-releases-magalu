"""Seleção dos N releases mais recentes, por período fiscal.

Ordenar por data de publicação embaralha a série — o release do 4T sai no ano
seguinte. Aqui a ordenação é sempre pelo período fiscal, e a saída é sempre em
ordem cronológica crescente.

Quando existem menos de N releases, a diferença é declarada em vez de silenciada:
silenciar faz o usuário acreditar que analisou mais período do que analisou.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from magalu_releases.models import Documento, Pendencia
from magalu_releases.vocabularios import Gatilho, Severidade, TipoDocumento


class SelecaoInvalida(Exception):
    """N fora da faixa utilizável."""


@dataclass(frozen=True, slots=True)
class ResultadoSelecao:
    selecionados: tuple[Documento, ...]
    n_pedido: int
    n_obtido: int
    descartados: tuple[Documento, ...]
    pendencias: tuple[Pendencia, ...]

    @property
    def faltou_documento(self) -> bool:
        return self.n_obtido < self.n_pedido

    @property
    def periodos(self) -> tuple[str, ...]:
        return tuple(d.periodo.canonico for d in self.selecionados if d.periodo)


def selecionar_releases(documentos, n: int) -> ResultadoSelecao:
    """Filtra releases, ordena por período fiscal e devolve os N mais recentes."""
    if not isinstance(n, int) or n < 1:
        raise SelecaoInvalida(f"N precisa ser inteiro >= 1, recebido {n!r}")

    descartados: list[Documento] = []
    candidatos: list[Documento] = []
    pendencias: list[Pendencia] = []
    contador = 0

    def nova_pendencia(tipo, severidade, descricao, referencias, acao):
        nonlocal contador
        contador += 1
        return Pendencia(
            pendencia_id=f"pen-{contador:04d}",
            tipo=tipo,
            severidade=severidade,
            descricao=descricao,
            referencias=tuple(referencias),
            acao_sugerida=acao,
        )

    for documento in documentos:
        if documento.tipo is not TipoDocumento.RELEASE_RESULTADOS:
            descartados.append(
                replace(
                    documento,
                    motivo_descarte=f"tipo {documento.tipo.value} não é release de resultados",
                )
            )
            if documento.tipo is TipoDocumento.NAO_CLASSIFICADO:
                pendencias.append(
                    nova_pendencia(
                        Gatilho.AMBIGUIDADE,
                        Severidade.MEDIA,
                        f"Documento {documento.documento_id!r} não pôde ser classificado "
                        f"pelo título {documento.titulo!r}; não foi incluído por eliminação",
                        [documento.documento_id],
                        "Confirmar manualmente se é release de resultados",
                    )
                )
            continue

        if documento.periodo is None:
            descartados.append(
                replace(documento, motivo_descarte="periodo fiscal indeterminado")
            )
            pendencias.append(
                nova_pendencia(
                    Gatilho.TRIMESTRE_VS_ACUMULADO,
                    Severidade.ALTA,
                    f"Release {documento.documento_id!r} sem periodo fiscal determinável "
                    "a partir do documento; não foi chutado",
                    [documento.documento_id],
                    "Abrir o PDF e identificar o período no cabeçalho",
                )
            )
            continue

        candidatos.append(documento)

    candidatos.sort(key=lambda d: d.periodo.chave_ordenacao)

    # Duplicata não é resolvida por escolha silenciosa: os dois lados ficam.
    por_periodo: dict[str, list[Documento]] = {}
    for documento in candidatos:
        por_periodo.setdefault(documento.periodo.canonico, []).append(documento)
    for canonico, grupo in por_periodo.items():
        if len(grupo) > 1:
            pendencias.append(
                nova_pendencia(
                    Gatilho.CONFLITO,
                    Severidade.ALTA,
                    f"Período {canonico} tem {len(grupo)} documentos duplicados; "
                    "ambos preservados, nenhum escolhido automaticamente",
                    [d.documento_id for d in grupo],
                    "Confirmar qual documento é o release oficial do período",
                )
            )

    periodos_ordenados = sorted(por_periodo, key=lambda c: por_periodo[c][0].periodo.chave_ordenacao)
    escolhidos_canonicos = periodos_ordenados[-n:] if n <= len(periodos_ordenados) else periodos_ordenados

    selecionados: list[Documento] = []
    for canonico in escolhidos_canonicos:
        selecionados.extend(por_periodo[canonico])
    selecionados.sort(key=lambda d: d.periodo.chave_ordenacao)

    pendencias.extend(
        nova_pendencia(
            Gatilho.AMBIGUIDADE,
            Severidade.BAIXA,
            f"Lacuna na sequência trimestral entre {anterior} e {atual}: "
            "o intervalo analisado não é contínuo",
            [],
            "Confirmar se o período intermediário existe na Central",
        )
        for anterior, atual in _lacunas(selecionados)
    )

    return ResultadoSelecao(
        selecionados=tuple(selecionados),
        n_pedido=n,
        n_obtido=len(escolhidos_canonicos),
        descartados=tuple(descartados),
        pendencias=tuple(pendencias),
    )


def _lacunas(selecionados) -> list[tuple[str, str]]:
    """Trimestres faltando entre dois períodos consecutivos da seleção."""
    trimestrais = [d.periodo for d in selecionados if d.periodo and d.periodo.trimestre]
    vistos = {p.canonico: p for p in trimestrais}
    ordenados = sorted(vistos.values(), key=lambda p: p.chave_ordenacao)
    buracos = []
    for anterior, atual in zip(ordenados, ordenados[1:]):
        indice_anterior = anterior.ano * 4 + anterior.trimestre
        indice_atual = atual.ano * 4 + atual.trimestre
        if indice_atual - indice_anterior > 1:
            buracos.append((anterior.canonico, atual.canonico))
    return buracos
