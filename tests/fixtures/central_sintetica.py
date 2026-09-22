"""HTML sintético que reproduz o layout real da Central de Resultados.

Capturado do site em 22/09/2026, reduzido a poucos períodos. A estrutura é a
que importa e é exatamente a do original:

- a listagem é uma tabela, uma linha por trimestre;
- o rótulo do período (`1T26`) fica na primeira célula da linha;
- os links são **opacos** — `Download.aspx?Arquivo=<token>`, âncora "PDF";
- o único lugar do markup que declara o tipo do documento é o `id` do controle
  ASP.NET: `..._rptResultados_linkArq_Release1T_0`.

A home entra aqui porque a URL da Central carrega um token de canal e precisa
ser descoberta a cada execução — congelá-la em configuração foi o que fez a
coleta quebrar com HTTP 500 quando o site mudou.
"""

HTML_HOME = """
<!DOCTYPE html>
<html lang="pt-br"><head><title>Magazine Luiza | Relações com Investidores</title></head>
<body>
  <section class="resultados">
    <a href="https://ri.magazineluiza.com.br/Download/Release-de-Resultado?=TOKEN-REL-2T26">
      Release de Resultado
    </a>
    <a href="/ListResultados/Central-de-Resultados?=0WX0bwP76pYcZvx+vXUnvg==">
      Ver todos os resultados
    </a>
  </section>
  <footer><a href="/ri/contato">Fale com o RI</a></footer>
</body></html>
"""

HTML_HOME_SEM_CENTRAL = """
<html><body><a href="/ri/contato">Fale com o RI</a></body></html>
"""


def _linha(rotulo: str, trimestre: int, indice: int, *, sem_periodo: bool = False) -> str:
    """Uma linha da tabela: período na primeira célula, cinco links opacos."""
    celula_periodo = "" if sem_periodo else rotulo
    arquivos = (
        ("Release", "PDF"),
        ("ITR", "PDF"),
        ("Apresentacao", "PDF"),
        ("Audio", "M4A"),
        ("Transcricao", "PDF"),
    )
    celulas = "".join(
        f'<td><a href="Download.aspx?Arquivo=TOKEN-{tipo.upper()}-{rotulo}" '
        f'id="ContentInternal_ContentPlaceHolderConteudo_rptResultados_'
        f'linkArq_{tipo}{trimestre}T_{indice}" target="_blank">{texto}</a></td>'
        for tipo, texto in arquivos
    )
    return (
        f'<tr id="ContentInternal_ContentPlaceHolderConteudo_rptResultados_'
        f'ResultadoArq{trimestre}Tri_{indice}">'
        f'<td resultado="ID-{rotulo}">{celula_periodo}</td>'
        f"{celulas}"
        f'<td style="display:none"><a class="btn btn-default" '
        f'href="ShowResultado.aspx?IdResultado=ID-{rotulo}">Saiba Mais</a></td>'
        f"</tr>"
    )


HTML_CENTRAL = f"""
<!DOCTYPE html>
<html lang="pt-br"><head><title>Central de Resultados</title></head>
<body>
  <table class="table"><tbody>
    {_linha("1T26", 1, 0)}
    {_linha("2T26", 2, 0)}
    {_linha("3T25", 3, 1)}
    {_linha("4T25", 4, 1)}
  </tbody></table>
  <div class="rodape">
    <a href="/ri/contato">Fale com o RI</a>
    <a href="javascript:__doPostBack('ctl00$paginacao','2')">Ver mais</a>
  </div>
</body></html>
"""

HTML_SEM_PERIODO = f"""
<html><body><table><tbody>
  {_linha("1T26", 1, 0, sem_periodo=True)}
</tbody></table></body></html>
"""
