"""Tests para funciones clave de resumen-rayados-diario.py"""
import importlib.util
import os
import sys
from unittest.mock import Mock, patch

import pytest

SCRIPT_DIR = os.path.expanduser("~/.hermes/scripts")
sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location(
    "resumen_rayados", os.path.join(SCRIPT_DIR, "resumen-rayados-diario.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

clean_url = mod.clean_url
clean_title = mod.clean_title
title_similar = mod.title_similar
dedupe = mod.dedupe
dedupe_by_title = mod.dedupe_by_title
domain_of = mod.domain_of
is_oficial = mod.is_oficial
smells_like_rumor = mod.smells_like_rumor
classify = mod.classify
retry_request = mod.retry_request
fetch_google_news = mod.fetch_google_news
fetch_rayados_com = mod.fetch_rayados_com


# ═══════════════════════════════════════════
# clean_url
# ═══════════════════════════════════════════


class TestCleanUrl:
    def test_limpia_oc_param(self):
        url = "https://news.google.com/rss/articles/CBMi?oc=5"
        result = clean_url(url)
        assert "oc=5" not in result

    def test_limpia_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = clean_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result

    def test_limpia_ceid_param(self):
        url = "https://news.google.com/rss/search?ceid=MX:es-419&hl=es"
        result = clean_url(url)
        assert "ceid=" not in result

    def test_url_limpia_sin_cambio(self):
        url = "https://example.com/clean/article"
        assert clean_url(url) == url

    def test_combinacion_params(self):
        url = (
            "https://news.google.com/rss/articles/CBMi?oc=5&utm_source=web&ceid=MX:es-419"
        )
        result = clean_url(url)
        assert "oc=" not in result
        assert "utm_" not in result
        assert "ceid=" not in result

    def test_quita_signos_sobrantes_final(self):
        url = "https://example.com/article?oc=5"
        result = clean_url(url)
        assert not result.endswith("?")
        assert not result.endswith("&")


# ═══════════════════════════════════════════
# clean_title
# ═══════════════════════════════════════════


class TestCleanTitle:
    def test_remueve_source_suffix(self):
        assert clean_title("Rayados ficha a crack - ESPN") == "Rayados ficha a crack"

    def test_multiples_dashes_solo_primer_corte(self):
        assert clean_title("Rayados - Tigres - Clásico Regio - Mediotiempo") == "Rayados"

    def test_reemplaza_brackets(self):
        assert clean_title("[OFICIAL] Rayados anuncia refuerzo") == "(OFICIAL) Rayados anuncia refuerzo"

    def test_sin_suffix_sin_cambio(self):
        assert clean_title("Rayados gana el clásico") == "Rayados gana el clásico"

    def test_titulo_vacio(self):
        assert clean_title("") == ""


# ═══════════════════════════════════════════
# title_similar
# ═══════════════════════════════════════════


class TestTitleSimilar:
    def test_titulos_identicos(self):
        assert title_similar("Rayados ficha crack", "Rayados ficha crack") is True

    def test_titulos_muy_similares(self):
        assert (
            title_similar(
                "Rayados ficha a crack mundial",
                "Rayados ficha a crack mundial",
            )
            is True
        )

    def test_titulos_diferentes(self):
        assert (
            title_similar(
                "Rayados gana el clásico",
                "Tigres anuncia nuevo estadio",
            )
            is False
        )

    def test_titulos_vacios(self):
        assert title_similar("", "Rayados") is False
        assert title_similar("Rayados", "") is False
        assert title_similar("", "") is False

    def test_threshold_personalizado(self):
        # Títulos similares pero con diferencia notable
        t1 = "Rayados ficha a Carlos Vela por 5 millones"
        t2 = "Rayados ficha a Carlos Vela por 10 millones"
        # Son similares, la única diferencia es el número
        assert title_similar(t1, t2, threshold=0.8) is True


# ═══════════════════════════════════════════
# dedupe
# ═══════════════════════════════════════════


class TestDedupe:
    def test_elimina_duplicados_por_link(self):
        items = [
            {"title": "Noticia 1", "link": "https://a.com/1"},
            {"title": "Noticia 1 dup", "link": "https://a.com/1"},
            {"title": "Noticia 2", "link": "https://a.com/2"},
        ]
        result = dedupe(items)
        assert len(result) == 2
        assert result[0]["title"] == "Noticia 1"
        assert result[1]["title"] == "Noticia 2"

    def test_sin_duplicados(self):
        items = [
            {"title": "A", "link": "https://a.com/a"},
            {"title": "B", "link": "https://a.com/b"},
        ]
        result = dedupe(items)
        assert len(result) == 2

    def test_lista_vacia(self):
        assert dedupe([]) == []


# ═══════════════════════════════════════════
# dedupe_by_title
# ═══════════════════════════════════════════


class TestDedupeByTitle:
    def test_elimina_titulos_similares(self):
        items = [
            {"title": "Rayados ficha a crack mundial"},
            {"title": "Rayados Ficha A Crack Mundial!!"},
            {"title": "Tigres pierde clásico"},
        ]
        result = dedupe_by_title(items)
        assert len(result) == 2

    def test_conserva_primero(self):
        items = [
            {"title": "Noticia original"},
            {"title": "Noticia original (copia)"},
        ]
        result = dedupe_by_title(items)
        assert len(result) == 1
        assert result[0]["title"] == "Noticia original"


# ═══════════════════════════════════════════
# domain_of
# ═══════════════════════════════════════════


class TestDomainOf:
    def test_extrae_dominio(self):
        assert domain_of("https://rayados.com/es/noticias") == "rayados.com"

    def test_ignora_www(self):
        assert domain_of("https://www.espn.com.mx/rayados") == "espn.com.mx"

    def test_ignora_protocolo_http(self):
        assert domain_of("http://mediotiempo.com/nota") == "mediotiempo.com"


# ═══════════════════════════════════════════
# is_oficial
# ═══════════════════════════════════════════


class TestIsOficial:
    def test_url_oficial(self):
        assert is_oficial("https://rayados.com/noticias/123") is True

    def test_url_no_oficial(self):
        assert is_oficial("https://espn.com.mx/rayados") is False


# ═══════════════════════════════════════════
# smells_like_rumor
# ═══════════════════════════════════════════


class TestSmellsLikeRumor:
    def test_detecta_rumor_explicito(self):
        assert smells_like_rumor("Rumor: Rayados busca fichaje bomba") is True

    def test_detecta_filtracion(self):
        assert smells_like_rumor("Filtran posible refuerzo de Rayados") is True

    def test_detecta_fichaje(self):
        assert smells_like_rumor("Rayados anuncia fichaje millonario") is True

    def test_titulo_objetivo_sin_rumor(self):
        assert smells_like_rumor("Rayados gana 3-0 al América") is False

    def test_case_insensitive(self):
        assert smells_like_rumor("RUMOR: Rayados ficha a Messi") is True


# ═══════════════════════════════════════════
# classify
# ═══════════════════════════════════════════


class TestClassify:
    def test_oficial_va_a_confirmadas(self):
        items = [
            {
                "title": "Noticia oficial",
                "link": "https://rayados.com/noticia",
                "source": "rayados.com",
                "oficial": True,
                "confiable": True,
                "rumor": False,
                "origin": "rayados.com",
                "category": "confirmadas",
            }
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0

    def test_rumor_va_a_rumores(self):
        items = [
            {
                "title": "Rumor de fichaje",
                "link": "https://mediotiempo.com/rumor",
                "source": "mediotiempo.com",
                "oficial": False,
                "confiable": True,
                "rumor": True,
                "origin": "google-news",
                "category": "confirmadas",
            }
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 0
        assert len(rumores) == 1

    def test_error_va_a_confirmadas(self):
        items = [
            {
                "title": "[Error rayados.com: timeout]",
                "link": "",
                "source": "rayados.com",
                "oficial": False,
                "confiable": False,
                "rumor": False,
                "origin": "Error",
                "category": "confirmadas",
            }
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0

    def test_confiable_sin_rumor_confirmada(self):
        items = [
            {
                "title": "Rayados gana",
                "link": "https://espn.com.mx/nota",
                "source": "ESPN",
                "oficial": False,
                "confiable": True,
                "rumor": False,
                "origin": "google-news",
                "category": "confirmadas",
            }
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0

    def test_desconocido_sin_rumor_confirmada(self):
        """Fuente desconocida pero título objetivo: confirmada igual."""
        items = [
            {
                "title": "Rayados anuncia nuevo patrocinador",
                "link": "https://blograndom.com/rayados",
                "source": "Blog Random",
                "oficial": False,
                "confiable": False,
                "rumor": False,
                "origin": "google-news",
                "category": "confirmadas",
            }
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0


# ═══════════════════════════════════════════
# retry_request
# ═══════════════════════════════════════════


class TestRetryRequest:
    URL = "https://example.com/api"

    def test_exito_primer_intento(self):
        mock_resp = Mock(status_code=200)
        with patch("requests.get", return_value=mock_resp) as mock_get:
            result = retry_request(self.URL)
            assert result == mock_resp
            assert mock_get.call_count == 1

    def test_retry_503_luego_exito(self):
        mock_503 = Mock(status_code=503)
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch(
            "requests.get", side_effect=[mock_503, mock_200]
        ) as mock_get:
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200
            assert mock_get.call_count == 2

    def test_retry_429_luego_exito(self):
        mock_429 = Mock(status_code=429)
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch("requests.get", side_effect=[mock_429, mock_200]):
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200

    def test_max_retries_agotados_503(self):
        import requests as req_mod

        mock_503 = Mock(status_code=503)
        mock_503.raise_for_status.side_effect = req_mod.HTTPError("503 Server Error")
        with patch("requests.get", return_value=mock_503) as mock_get:
            with patch("time.sleep", return_value=None):
                with pytest.raises(req_mod.HTTPError):
                    retry_request(self.URL, max_attempts=3)
            assert mock_get.call_count == 3

    def test_connection_error_retry(self):
        import requests as req_mod

        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch(
            "requests.get",
            side_effect=[req_mod.ConnectionError("fail"), mock_200],
        ) as mock_get:
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200
            assert mock_get.call_count == 2

    def test_timeout_retry(self):
        import requests as req_mod

        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch(
            "requests.get", side_effect=[req_mod.Timeout("timeout"), mock_200]
        ) as mock_get:
            with patch("time.sleep", return_value=None):
                result = retry_request(self.URL)
            assert result == mock_200
            assert mock_get.call_count == 2

    def test_http_4xx_no_retry(self):
        mock_404 = Mock(status_code=404)
        mock_404.raise_for_status.side_effect = Exception("HTTPError")
        with patch("requests.get", return_value=mock_404):
            with pytest.raises(Exception):
                retry_request(self.URL)

    def test_backoff_creciente(self):
        mock_503 = Mock(status_code=503)
        with patch("requests.get", return_value=mock_503):
            with patch("time.sleep") as mock_sleep:
                retry_request(self.URL, max_attempts=3)
                assert mock_sleep.call_count == 2
                sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
                assert 0 <= sleep_times[0] < 1.5
                assert 1.5 <= sleep_times[1] < 3.0

    def test_con_headers_personalizados(self):
        mock_resp = Mock(status_code=200)
        mock_resp.raise_for_status.return_value = None
        with patch("requests.get", return_value=mock_resp) as mock_get:
            custom_headers = {"Authorization": "Bearer token123"}
            result = retry_request(self.URL, headers=custom_headers)
            assert result == mock_resp
            kwargs = mock_get.call_args.kwargs
            assert kwargs["headers"] == custom_headers


# ═══════════════════════════════════════════
# fetch_google_news
# ═══════════════════════════════════════════


GOOGLE_NEWS_ENTRIES = [
    Mock(
        title="Rayados gana 3-0 al América",
        link="https://news.google.com/rss/articles/1?oc=5",
        source=Mock(title="ESPN"),
    ),
    Mock(
        title="Rumor: Rayados busca fichaje estrella - Mediotiempo",
        link="https://news.google.com/rss/articles/2",
        source=Mock(title="Mediotiempo"),
    ),
]
# Configure .get() for Mock entries (feedparser entries support dict-like .get)
for entry in GOOGLE_NEWS_ENTRIES:
    entry.get = lambda key, default="", _entry=entry: getattr(_entry, key, default)


class TestFetchGoogleNews:
    def test_parse_rss_exitoso(self):
        """Parse feedparser devuelve items correctamente."""
        mock_feed = Mock()
        mock_feed.entries = GOOGLE_NEWS_ENTRIES[:1]
        with patch.object(mod.feedparser, "parse", return_value=mock_feed):
            items = fetch_google_news("Rayados", "confirmadas")
            assert len(items) == 1
            item = items[0]
            assert "Rayados" in item["title"]
            assert item["origin"] == "google-news"
            assert item["category"] == "confirmadas"

    def test_detecta_oficial(self):
        mock_feed = Mock()
        entry_oficial = Mock(
            title="Noticia oficial",
            link="https://rayados.com/es/noticias/123",
            source=Mock(title="rayados.com"),
        )
        entry_oficial.get = lambda key, default="", _e=entry_oficial: getattr(_e, key, default)
        mock_feed.entries = [entry_oficial]
        with patch.object(mod.feedparser, "parse", return_value=mock_feed):
            items = fetch_google_news("Rayados", "confirmadas")
            assert len(items) == 1
            assert items[0]["oficial"] is True

    def test_excepcion_retorna_error_item(self):
        with patch.object(
            mod.feedparser, "parse", side_effect=Exception("timeout")
        ):
            items = fetch_google_news("Rayados", "confirmadas")
            assert len(items) == 1
            assert items[0]["title"].startswith("[Error")


# ═══════════════════════════════════════════
# fetch_rayados_com
# ═══════════════════════════════════════════


RAYADOS_HTML = """
<html><body>
<ul>
<li>
  <a href="/es/noticias/12345">Noticia 12345</a>
  <h2>Rayados cierra fichaje de lujo para el Apertura</h2>
</li>
<li>
  <a href="/es/noticias/12346">Noticia 12346</a>
  <h3>Convocatoria confirmada para duelo de jornada 5</h3>
</li>
</ul>
</body></html>
"""


class TestFetchRayadosCom:
    def test_parse_html_exitoso(self):
        mock_resp = Mock()
        mock_resp.text = RAYADOS_HTML
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 2
            assert items[0]["title"] == "Rayados cierra fichaje de lujo para el Apertura"
            assert items[0]["source"] == "rayados.com"
            assert items[0]["oficial"] is True
            assert "rayados.com/es/noticias/12345" in items[0]["link"]

    def test_excepcion_retorna_error_item(self):
        with patch.object(
            mod,
            "retry_request",
            side_effect=Exception("Connection refused"),
        ):
            items = fetch_rayados_com()
            assert len(items) == 1
            assert items[0]["title"].startswith("[Error rayados.com")

    def test_items_sin_heading_usan_title_attr(self):
        html = """
        <html><body><ul>
        <li>
          <a href="/es/noticias/789" title="Título desde atributo title"></a>
        </li>
        </ul></body></html>
        """
        mock_resp = Mock()
        mock_resp.text = html
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 1
            assert items[0]["title"] == "Título desde atributo title"

    def test_titulos_cortos_ignorados(self):
        """Títulos con menos de 10 caracteres se ignoran."""
        html = """
        <html><body><ul>
        <li>
          <a href="/es/noticias/1">Noticia 1</a>
          <h2>Corto</h2>
        </li>
        <li>
          <a href="/es/noticias/2">Noticia 2</a>
          <h2>Este título sí es suficientemente largo</h2>
        </li>
        </ul></body></html>
        """
        mock_resp = Mock()
        mock_resp.text = html
        with patch.object(mod, "retry_request", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 1