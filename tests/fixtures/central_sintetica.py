"""HTML sintético que reproduz o layout descrito da Central de Resultados.

A página real usa ASP.NET WebForms e agrupa os documentos por trimestre. Esta
fixture reproduz esse arranjo — cabeçalho de período seguido dos seus documentos
— sem copiar markup que ainda não foi capturado do site.

A fixture real, quando capturada, substitui esta nos testes de integração.
"""

HTML_CENTRAL = """
<!DOCTYPE html>
<html lang="pt-br"><head><title>Central de Resultados</title></head>
<body>
  <div class="conteudo">
    <div class="resultado-item">
      <h3 class="periodo">2T26</h3>
      <ul>
        <li><a href="/download/release-2t26.pdf">Release de Resultado</a></li>
        <li><a href="/download/itr-2t26.pdf">ITR</a></li>
        <li><a href="/download/apresentacao-2t26.pdf">Apresenta&ccedil;&atilde;o</a></li>
        <li><a href="/download/transcricao-2t26.pdf">Transcri&ccedil;&atilde;o</a></li>
        <li><a href="https://audio.exemplo/2t26">&Aacute;udio da Teleconfer&ecirc;ncia</a></li>
      </ul>
    </div>
    <div class="resultado-item">
      <h3 class="periodo">1T26</h3>
      <ul>
        <li><a href="/download/release-1t26.pdf">Release de Resultado</a></li>
        <li><a href="/download/itr-1t26.pdf">ITR</a></li>
        <li><a href="/download/apresentacao-1t26.pdf">Apresenta&ccedil;&atilde;o</a></li>
      </ul>
    </div>
    <div class="resultado-item">
      <h3 class="periodo">4T25</h3>
      <ul>
        <li><a href="/download/release-4t25.pdf">Release de Resultado</a></li>
        <li><a href="/download/dfp-2025.pdf">DFP</a></li>
        <li><a href="/download/apresentacao-4t25.pdf">Apresenta&ccedil;&atilde;o</a></li>
      </ul>
    </div>
    <div class="resultado-item">
      <h3 class="periodo">3T25</h3>
      <ul>
        <li><a href="/download/release-3t25.pdf">Release de Resultados 3T25</a></li>
        <li><a href="/download/itr-3t25.pdf">ITR</a></li>
      </ul>
    </div>
    <div class="rodape">
      <a href="/ri/contato">Fale com o RI</a>
      <a href="javascript:__doPostBack('ctl00$paginacao','2')">Ver mais</a>
    </div>
  </div>
</body></html>
"""

HTML_SEM_PERIODO = """
<html><body>
  <ul>
    <li><a href="/download/release-solto.pdf">Release de Resultado</a></li>
  </ul>
</body></html>
"""
