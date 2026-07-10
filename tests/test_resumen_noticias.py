"""Tests para funciones clave de resumen-noticias-diario.py"""
import importlib.util  # noqa: E402
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add script dir to path para importar
SCRIPT_DIR = os.path.expanduser("~/.hermes/scripts")
sys.path.insert(0, SCRIPT_DIR)

# Import functions under test
# Usamos import directo del script (sin .py)

spec = importlib.util.spec_from_file_location(
    "resumen_noticias", os.path.join(SCRIPT_DIR, "resumen-noticias-diario.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

clean_title = mod.clean_title
escape_link = mod.escape_link
retry_request = mod.retry_request
fetch_rss = mod.fetch_rss


# ═══════════════════════════════════════════
# clean_title
# ═══════════════════════════════════════════


class TestCleanTitle:
    def test_remueve_source_suffix(self):
        """Quita ' - SourceName' del final"""
        assert clean_title("Breaking News - Reuters") == "Breaking News"
        assert clean_title("Markets Crash - Financial Times") == "Markets Crash"

    def test_multiples_dashes_no_rompe(self):
        """Títulos con múltiples ' - ' solo cortan primero"""
        assert clean_title("US - China Trade - War Escalates - CNN") == "US"

    def test_reemplaza_brackets(self):
        """[ y ] se convierten a ( y )"""
        assert clean_title("Elon [Musk] speaks") == "Elon (Musk) speaks"
        assert clean_title("[BREAKING] News") == "(BREAKING) News"

    def test_sin_suffix_sin_cambio(self):
        """Título sin ' - ' queda igual (solo brackets cambiados)"""
        assert clean_title("Plain title") == "Plain title"

    def test_titulo_vacio(self):
        assert clean_title("") == ""


# ═══════════════════════════════════════════
# escape_link
# ═══════════════════════════════════════════


class TestEscapeLink:
    def test_limpia_oc_param(self):
        link = "https://news.google.com/rss/articles/CBMi?oc=5"
        result = escape_link(link)
        assert "oc=5" not in result

    def test_limpia_utm_params(self):
        link = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = escape_link(link)
        assert "utm_source" not in result
        assert "utm_medium" not in result

    def test_limpia_ceid_param(self):
        link = "https://news.google.com/rss/search?ceid=US:en&hl=en"
        result = escape_link(link)
        assert "ceid=" not in result

    def test_escapa_parentesis_cierre(self):
        """Reemplaza ) con %29 en URLs"""
        link = "https://example.com/path(1)/article"
        result = escape_link(link)
        assert ")" not in result
        assert "%29" in result

    def test_limpia_query_vacia_al_final(self):
        """Si queda '?' o '&' al final, se quita"""
        link = "https://example.com/article?utm_source=x"
        result = escape_link(link)
        assert not result.endswith("?")
        assert not result.endswith("&")

    def test_link_limpio_sin_cambio(self):
        link = "https://example.com/clean/article"
        assert escape_link(link) == link

    def test_combinacion_params(self):
        """Todos los params juntos"""
        link = "https://news.google.com/rss/articles/CBMi?oc=5&utm_source=web&ceid=US:en&hl=en"
        result = escape_link(link)
        assert "oc=" not in result
        assert "utm_" not in result
        assert "ceid=" not in result
        assert result.startswith("https://news.google.com")


# ═══════════════════════════════════════════
# retry_request
# ═══════════════════════════════════════════


class TestRetryRequest:
    URL = "https://example.com/rss"

    def test_exito_primer_intento(self):
        """Respuesta 200 al primer intento"""
        mock_resp = Mock(status_code=200)
        with patch("requests.get", return_value=mock_resp) as mock_get:
            result = retry_request(self.URL)
            assert result == mock_resp
            assert mock_get.call_count == 1

    def test_retry_503_luego_exito(self):
        """Falla con 503, reintenta, éxito"""
        mock_503 = Mock(status_code=503)
        mock_200 = Mock(status_code=200)
        mock_503.raise_for_status.side_effect = Exception("no llamar")
        mock_200.raise_for_status.return_value = None
        with patch("requests.get", side_effect=[mock_503, mock_200]) as mock_get:
            with patch("time.sleep", return_value=None):  # no esperar
                result = retry_request(self.URL)
            assert result == mock_200
            assert mock_get.call_count == 2

    def test_retry_429_luego_exito(self):
        """Rate limit → reintenta → éxito"""
        mock_429 = Mock(status_code=429)
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch("requests.get", side_effect=[mock_429, mock_200]):
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200

    def test_max_retries_agotados_503(self):
        """3 intentos, todos 503 → lanza HTTPError en el último"""
        import requests as req_mod
        mock_503 = Mock(status_code=503)
        mock_503.raise_for_status.side_effect = req_mod.HTTPError("503 Server Error")
        with patch("requests.get", return_value=mock_503) as mock_get:
            with patch("time.sleep", return_value=None):
                with pytest.raises(req_mod.HTTPError):
                    retry_request(self.URL, max_attempts=3)
            assert mock_get.call_count == 3

    def test_connection_error_retry(self):
        """ConnectionError → reintenta → éxito"""
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        import requests as req_mod

        with patch(
            "requests.get", side_effect=[req_mod.ConnectionError("timeout"), mock_200]
        ) as mock_get:
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200
            assert mock_get.call_count == 2

    def test_timeout_retry(self):
        """Timeout → reintenta → éxito"""
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        import requests as req_mod

        with patch("requests.get", side_effect=[req_mod.Timeout("timeout"), mock_200]):
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200

    def test_connection_error_agota_retries(self):
        """3 ConnectionErrors → lanza excepción"""
        import requests as req_mod

        with patch("requests.get", side_effect=req_mod.ConnectionError("fail")):
            with patch("time.sleep", return_value=None):
                with pytest.raises(req_mod.ConnectionError):
                    retry_request(self.URL, max_attempts=2)

    def test_http_4xx_no_retry(self):
        """HTTPError 4xx → no reintenta, lanza inmediato"""
        mock_404 = Mock(status_code=404)
        mock_404.raise_for_status.side_effect = Exception("HTTPError")  # cualquier excepción

        with patch("requests.get", return_value=mock_404):
            # 404 no está en RETRY_STATUS, así que va a raise_for_status
            # y lanza. Capturamos con pytest.raises genérico.
            with pytest.raises(Exception):
                retry_request(self.URL)

    def test_backoff_creciente(self):
        """Verifica que el backoff usa 2^attempt"""
        mock_503 = Mock(status_code=503)
        with patch("requests.get", return_value=mock_503):
            with patch("time.sleep") as mock_sleep:
                retry_request(self.URL, max_attempts=3)
                # Llamadas: attempt 0 → sleep(2^0 + jitter ≈ 1.x)
                #           attempt 1 → sleep(2^1 + jitter ≈ 2.x)
                # attempt 2 → no sleep (último intento)
                assert mock_sleep.call_count == 2
                sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
                assert 0 <= sleep_times[0] < 1.5  # 2^0 + jitter [0, 0.5)
                assert 1.5 <= sleep_times[1] < 3.0  # 2^1 + jitter [0, 0.5)


# ═══════════════════════════════════════════
# fetch_rss
# ═══════════════════════════════════════════

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>First Article Title</title>
      <link>https://example.com/first</link>
    </item>
    <item>
      <title>Second Article</title>
      <link>https://example.com/second</link>
    </item>
    <item>
      <title>Third Story - With Dash</title>
      <link>https://example.com/third</link>
    </item>
    <item>
      <title>Fourth Item</title>
      <link>https://example.com/fourth</link>
    </item>
    <item>
      <title>Fifth Extra</title>
      <link>https://example.com/fifth</link>
    </item>
  </channel>
</rss>"""

# Google News boilerplate (debe ser ignorado)
GN_BOILERPLATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>"Some search query" when:24h</title>
      <link>https://news.google.com/rss/search?q=site:reuters.com</link>
    </item>
    <item>
      <title>Real Article</title>
      <link>https://example.com/real</link>
    </item>
  </channel>
</rss>"""

RDF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:rss="http://purl.org/rss/1.0/"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel rdf:about="https://example.com/rdf">
    <title>RDF Feed</title>
  </channel>
  <rss:item rdf:about="https://example.com/rdf-article-1">
    <rss:title>RDF Article One</rss:title>
    <rss:link>https://example.com/rdf/1</rss:link>
  </rss:item>
  <rss:item rdf:about="https://example.com/rdf-article-2">
    <rss:title>RDF Article Two</rss:title>
    <rss:link>https://example.com/rdf/2</rss:link>
  </rss:item>
</rdf:RDF>"""


class TestFetchRss:
    URL = "https://example.com/rss"

    def test_parse_rss_estandar(self):
        """Parse RSS estándar con items"""
        mock_resp = Mock()
        mock_resp.content = RSS_XML.encode("utf-8")
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 4  # max 4 items
            assert items[0] == ("First Article Title", "https://example.com/first")
            assert items[1] == ("Second Article", "https://example.com/second")

    def test_filtra_boilerplate_google_news(self):
        """Ignora títulos que empiezan con \" y contienen ' when:'"""
        mock_resp = Mock()
        mock_resp.content = GN_BOILERPLATE_XML.encode("utf-8")
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 1
            assert items[0][0] == "Real Article"

    def test_retry_request_retorna_none(self):
        """Si retry_request retorna None → lista vacía"""
        with patch.object(mod, "retry_request", return_value=None):
            items = fetch_rss(self.URL)
            assert items == []

    def test_parse_rdf_feed(self):
        """Parse feed RDF (DW, etc.)"""
        mock_resp = Mock()
        mock_resp.content = RDF_XML.encode("utf-8")
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 2
            assert items[0] == ("RDF Article One", "https://example.com/rdf/1")
            assert items[1] == ("RDF Article Two", "https://example.com/rdf/2")

    def test_excepcion_retorna_lista_vacia(self):
        """Cualquier excepción → []"""
        with patch.object(mod, "retry_request", side_effect=Exception("boom")):
            items = fetch_rss(self.URL)
            assert items == []

    def test_xml_malformado(self):
        """XML inválido → []"""

        mock_resp = Mock()
        mock_resp.content = b"not valid xml <<<"
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert items == []

    def test_link_con_atributo_href(self):
        """Link tipo <link href='...'/> (Atom style)"""
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
        <item><title>Atom Link</title><link href="https://example.com/atom"/></item>
        </channel></rss>"""
        mock_resp = Mock()
        mock_resp.content = xml.encode("utf-8")
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 1
            assert items[0][1] == "https://example.com/atom"

    def test_item_sin_titulo_ignorado(self):
        """Items sin <title> se ignoran"""
        xml = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
        <item><link>https://example.com/notitle</link></item>
        <item><title>Has Title</title><link>https://example.com/hastitle</link></item>
        </channel></rss>"""
        mock_resp = Mock()
        mock_resp.content = xml.encode("utf-8")
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 1
            assert items[0][0] == "Has Title"
