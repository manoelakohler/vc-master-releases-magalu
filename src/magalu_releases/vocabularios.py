"""Vocabulários controlados do contrato de dados.

Um valor fora destas listas é erro, não extensão informal: é a lista fechada que
impede que "lucro líquido" e "lucro líquido ajustado" acabem na mesma série.
"""

from __future__ import annotations

from enum import StrEnum


class Segmento(StrEnum):
    """`marketplace` e `3p` coexistem porque nem todo release os usa como sinônimo."""

    CONSOLIDADO = "consolidado"
    LOJAS_FISICAS = "lojas_fisicas"
    ECOMMERCE = "ecommerce"
    MARKETPLACE = "marketplace"
    UM_P = "1p"
    TRES_P = "3p"
    SERVICOS = "servicos"
    OUTRO = "outro"


class Base(StrEnum):
    """`INDEFINIDO` existe para não forçar escolha entre ajustado e reportado."""

    REPORTADO = "reportado"
    AJUSTADO = "ajustado"
    INDEFINIDO = "indefinido"


class Periodicidade(StrEnum):
    TRIMESTRE = "trimestre"
    ACUMULADO = "acumulado"
    ANUAL = "anual"


class TipoValor(StrEnum):
    """`PERCENTUAL` é um nível; `VARIACAO_PP` é a diferença entre dois níveis."""

    ABSOLUTO = "absoluto"
    PERCENTUAL = "percentual"
    VARIACAO_ABS = "variacao_abs"
    VARIACAO_PCT = "variacao_pct"
    VARIACAO_PP = "variacao_pp"
    TEXTO = "texto"


class Confianca(StrEnum):
    """Ordenável: `BAIXA < MEDIA < ALTA`.

    A comparação alfabética herdada de `str` daria "alta" < "baixa", que é o
    contrário do pretendido — por isso os operadores são redefinidos.
    """

    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"

    @property
    def nivel(self) -> int:
        return _NIVEIS_CONFIANCA[self]

    def __lt__(self, outro: object) -> bool:
        if not isinstance(outro, Confianca):
            return NotImplemented
        return self.nivel < outro.nivel

    def __le__(self, outro: object) -> bool:
        if not isinstance(outro, Confianca):
            return NotImplemented
        return self.nivel <= outro.nivel

    def __gt__(self, outro: object) -> bool:
        if not isinstance(outro, Confianca):
            return NotImplemented
        return self.nivel > outro.nivel

    def __ge__(self, outro: object) -> bool:
        if not isinstance(outro, Confianca):
            return NotImplemented
        return self.nivel >= outro.nivel


_NIVEIS_CONFIANCA = {Confianca.BAIXA: 0, Confianca.MEDIA: 1, Confianca.ALTA: 2}


def pior_confianca(*confiancas: Confianca) -> Confianca:
    """A confiança de um conjunto é a do seu elo mais fraco.

    Uma variação herda a fragilidade da pior das pontas, e uma variação frágil
    parece tão sólida quanto qualquer outra na planilha.
    """
    if not confiancas:
        raise ValueError("pior_confianca exige ao menos uma confiança")
    return min(confiancas, key=lambda c: c.nivel)


class Gatilho(StrEnum):
    """Os dez gatilhos de revisão humana definidos pela skill."""

    CONFIANCA_BAIXA = "confianca_baixa"
    CONFLITO = "conflito"
    AMBIGUIDADE = "ambiguidade"
    UNIDADE_NAO_CLARA = "unidade_nao_clara"
    TABELA_SEM_ESTRUTURA = "tabela_sem_estrutura"
    AJUSTADO_VS_REPORTADO = "ajustado_vs_reportado"
    TRIMESTRE_VS_ACUMULADO = "trimestre_vs_acumulado"
    NARRATIVA_VS_TABELA = "narrativa_vs_tabela"
    CONCLUSAO_QUALITATIVA = "conclusao_qualitativa"
    RISCO_RECOMENDACAO = "risco_recomendacao"


class TipoDocumento(StrEnum):
    """Só `RELEASE_RESULTADOS` entra na análise.

    `NAO_CLASSIFICADO` nunca é promovido a release por eliminação: incluir um ITR
    como se fosse release contamina a comparação inteira.
    """

    RELEASE_RESULTADOS = "release_resultados"
    ITR_DFP = "itr_dfp"
    DEMONSTRACOES_FINANCEIRAS = "demonstracoes_financeiras"
    APRESENTACAO = "apresentacao"
    TRANSCRICAO = "transcricao"
    AUDIO_TELECONFERENCIA = "audio_teleconferencia"
    FATO_RELEVANTE = "fato_relevante"
    COMUNICADO = "comunicado"
    FORMULARIO_REFERENCIA = "formulario_referencia"
    SUSTENTABILIDADE = "sustentabilidade"
    PLANILHA = "planilha"
    NAO_CLASSIFICADO = "nao_classificado"


class Severidade(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class ResultadoCheck(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ALERTA = "ALERTA"


class BaseComparacao(StrEnum):
    """"Cresceu 12%" significa coisas diferentes conforme a base — por isso é obrigatória."""

    PERIODO_ANTERIOR = "periodo_anterior"
    MESMO_TRIMESTRE_ANO_ANTERIOR = "mesmo_trimestre_ano_anterior"
