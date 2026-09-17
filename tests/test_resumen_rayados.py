"""Tests para funciones clave de resumen-rayados-diario.py"""

import importlib.util
import os
import sys
from unittest.mock import Mock, patch

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location(
    "resumen_rayados",
    os.path.join(SCRIPT_DIR, "src", "scripts", "resumen_rayados_diario.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

clean_url = mod.clean_url
clean_title = mod.clean_title
canonical_title = mod.canonical_title
title_similar = mod.title_similar
dedupe = mod.dedupe
dedupe_by_title = mod.dedupe_by_title
domain_of = mod.domain_of
is_oficial = mod.is_oficial
smells_like_rumor = mod.smells_like_rumor
classify = mod.classify
fetch_google_news = mod.fetch_google_news
fetch_rayados_com = mod.fetch_rayados_com
fetch_rayados_detail = mod.fetch_rayados_detail
enrich_rayados_items = mod.enrich_rayados_items
format_item_line = mod.format_item_line
NewsItem = mod.NewsItem

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
        url = "https://news.google.com/rss/articles/CBMi?oc=5&utm_source=web&ceid=MX:es-419"
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
        assert (
            clean_title("[OFICIAL] Rayados anuncia refuerzo")
            == "(OFICIAL) Rayados anuncia refuerzo"
        )

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
            NewsItem(title="Noticia 1", link="https://a.com/1"),
            NewsItem(title="Noticia 1 dup", link="https://a.com/1"),
            NewsItem(title="Noticia 2", link="https://a.com/2"),
        ]
        result = dedupe(items)
        assert len(result) == 2
        assert result[0].title == "Noticia 1"
        assert result[1].title == "Noticia 2"

    def test_sin_duplicados(self):
        items = [
            NewsItem(title="A", link="https://a.com/a"),
            NewsItem(title="B", link="https://a.com/b"),
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
            NewsItem(title="Rayados ficha a crack mundial"),
            NewsItem(title="Rayados Ficha A Crack Mundial!!"),
            NewsItem(title="Tigres pierde clásico"),
        ]
        result = dedupe_by_title(items)
        assert len(result) == 2

    def test_conserva_primero(self):
        items = [
            NewsItem(title="Noticia original"),
            NewsItem(title="Noticia original (copia)"),
        ]
        result = dedupe_by_title(items)
        assert len(result) == 1
        assert result[0].title == "Noticia original"


# ═══════════════════════════════════════════
# canonical_title + dedupe lineal (#69)
# ═══════════════════════════════════════════


class TestCanonicalTitle:
    def test_normaliza_mayusculas_y_puntuacion(self):
        assert canonical_title("Rayados Ficha A Crack Mundial!!") == "rayadosfichaacrackmundial"

    def test_vacio(self):
        assert canonical_title("") == ""


class TestDedupeLineal:
    def test_exactos_colapsan_por_hash(self):
        items = [
            NewsItem(title="Rayados gana 2-0"),
            NewsItem(title="Rayados GANA 2 0!!"),
            NewsItem(title="Otra noticia"),
        ]
        result = dedupe_by_title(items)
        assert [i.title for i in result] == ["Rayados gana 2-0", "Otra noticia"]

    def test_titulos_vacios_nunca_colapsan(self):
        items = [NewsItem(title=""), NewsItem(title=""), NewsItem(title="X")]
        assert len(dedupe_by_title(items)) == 3

    def test_threshold_1_solo_exactos(self):
        items = [
            NewsItem(title="Noticia original"),
            NewsItem(title="Noticia original (copia)"),
            NewsItem(title="Noticia original"),
        ]
        result = dedupe_by_title(items, threshold=1.0)
        assert [i.title for i in result] == ["Noticia original", "Noticia original (copia)"]

    def test_comparaciones_acotadas_no_cuadraticas(self, monkeypatch):
        calls = {"n": 0}
        real = mod.title_similar

        def counting(t1, t2, threshold=0.85):
            calls["n"] += 1
            return real(t1, t2, threshold)

        monkeypatch.setattr(mod, "title_similar", counting)
        items = [NewsItem(title=f"Asunto-{i:04d}-abc relleno dedupe") for i in range(200)]
        result = mod.dedupe_by_title(items)
        assert len(result) == 200
        assert calls["n"] < 1000


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
            NewsItem(
                title="Noticia oficial",
                link="https://rayados.com/noticia",
                source="rayados.com",
                oficial=True,
                confiable=True,
                origin="rayados.com",
                category="confirmadas",
            )
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0

    def test_rumor_va_a_rumores(self):
        items = [
            NewsItem(
                title="Rumor de fichaje",
                link="https://mediotiempo.com/rumor",
                source="mediotiempo.com",
                confiable=True,
                rumor=True,
                origin="google-news",
                category="confirmadas",
            )
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 0
        assert len(rumores) == 1

    def test_error_va_a_confirmadas(self):
        items = [
            NewsItem(
                title="[Error rayados.com: timeout]",
                source="rayados.com",
                origin="Error",
                category="confirmadas",
            )
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0

    def test_confiable_sin_rumor_confirmada(self):
        items = [
            NewsItem(
                title="Rayados gana",
                link="https://espn.com.mx/nota",
                source="ESPN",
                confiable=True,
                origin="google-news",
                category="confirmadas",
            )
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0

    def test_desconocido_sin_rumor_confirmada(self):
        """Fuente desconocida pero título objetivo: confirmada igual."""
        items = [
            NewsItem(
                title="Rayados anuncia nuevo patrocinador",
                link="https://blograndom.com/rayados",
                source="Blog Random",
                origin="google-news",
                category="confirmadas",
            )
        ]
        confirmadas, rumores = classify(items)
        assert len(confirmadas) == 1
        assert len(rumores) == 0


# ═══════════════════════════════════════════
# fetch_google_news
# ═══════════════════════════════════════════

GOOGLE_NEWS_ENTRIES = [
    Mock(
        title="Rayados gana 3-0 al América",
        link="https://news.google.com/rss/articles/1?oc=5",
        source=Mock(title="ESPN"),
        author="ESPN",
    ),
    Mock(
        title="Rumor: Rayados busca fichaje estrella - Mediotiempo",
        link="https://news.google.com/rss/articles/2",
        source=Mock(title="Mediotiempo"),
        author="Mediotiempo",
    ),
]


def _mock_get_factory(mock_obj):
    """Crea función .get() para Mock que emula dict.get usando atributos."""

    def _get(key, default=""):
        return getattr(mock_obj, key, default)

    return _get


# Configure .get() for Mock entries and their nested source mocks
for entry in GOOGLE_NEWS_ENTRIES:
    entry.get = _mock_get_factory(entry)
    if hasattr(entry, "source") and hasattr(entry.source, "title"):
        entry.source.get = _mock_get_factory(entry.source)


class TestFetchGoogleNews:
    def test_parse_rss_exitoso(self):
        """Parse feedparser devuelve items correctamente."""
        mock_feed = Mock()
        mock_feed.entries = GOOGLE_NEWS_ENTRIES[:1]
        with patch.object(mod.feedparser, "parse", return_value=mock_feed):
            items = fetch_google_news("Rayados", "confirmadas")
            assert len(items) == 1
            item = items[0]
            assert "Rayados" in item.title
            assert item.origin == "google-news"
            assert item.category == "confirmadas"

    def test_detecta_oficial(self):
        mock_feed = Mock()
        source_mock = Mock(title="rayados.com")
        source_mock.get = lambda key, default="", _s=source_mock: getattr(_s, key, default)
        entry_oficial = Mock(
            title="Noticia oficial",
            link="https://rayados.com/es/noticias/123",
            source=source_mock,
            author="rayados.com",
        )
        entry_oficial.get = lambda key, default="", _e=entry_oficial: getattr(_e, key, default)
        mock_feed.entries = [entry_oficial]
        with patch.object(mod.feedparser, "parse", return_value=mock_feed):
            items = fetch_google_news("Rayados", "confirmadas")
            assert len(items) == 1
            assert items[0].oficial is True

    def test_excepcion_retorna_error_item(self):
        with patch.object(mod.feedparser, "parse", side_effect=Exception("timeout")):
            items = fetch_google_news("Rayados", "confirmadas")
            assert len(items) == 1
            assert items[0].title.startswith("[Error")


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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 2
            assert items[0].title == "Rayados cierra fichaje de lujo para el Apertura"
            assert items[0].source == "rayados.com"
            assert items[0].oficial is True
            assert "rayados.com/es/noticias/12345" in items[0].link

    def test_excepcion_retorna_error_item(self):
        with patch.object(
            mod,
            "retry_request",
            side_effect=Exception("Connection refused"),
        ):
            items = fetch_rayados_com()
            assert len(items) == 1
            assert items[0].title.startswith("[Error rayados.com")

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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 1
            assert items[0].title == "Título desde atributo title"

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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 1


# ═══════════════════════════════════════════
# Fecha verificada y filtro 48h (issue #128)
# ═══════════════════════════════════════════


class TestRayadosSinFechaVerificada:
    def test_items_salen_sin_published(self):
        mock_resp = Mock()
        mock_resp.text = RAYADOS_HTML
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rayados_com()
            assert len(items) == 2
            assert all(i.published is None for i in items)
            assert all(i.author is None for i in items)

    def test_sin_fecha_se_descarta_con_drop(self):
        from hermes_common import filter_by_max_age

        mock_resp = Mock()
        mock_resp.text = RAYADOS_HTML
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rayados_com()
            assert filter_by_max_age(items, missing="drop") == []

    def test_con_fecha_reciente_se_conserva(self):
        from datetime import datetime, timedelta, timezone

        from hermes_common import filter_by_max_age

        now = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        items = [
            NewsItem(
                title="Nota oficial reciente",
                link="https://www.rayados.com/es/noticias/1/x/",
                source="rayados.com",
                oficial=True,
                published=now - timedelta(hours=5),
                author="Redacción",
            )
        ]
        kept = filter_by_max_age(items, missing="drop", now=now)
        assert len(kept) == 1


RAYADOS_DETAIL_HTML = """
<html><head>
<meta property="article:published_time" content="2026-09-14T10:00:00+00:00" />
<meta name="author" content="Prensa Rayados" />
</head><body><h1>Nota</h1></body></html>
"""


class TestFetchRayadosDetail:
    def test_fecha_y_autor(self):
        mock_resp = Mock()
        mock_resp.text = RAYADOS_DETAIL_HTML
        with patch.object(mod, "retry_request", return_value=mock_resp):
            published, author = fetch_rayados_detail("https://www.rayados.com/es/noticias/1/x/")
            assert published is not None
            assert (published.year, published.month, published.day) == (2026, 9, 14)
            assert author == "Prensa Rayados"

    def test_sin_tags_retorna_nones(self):
        mock_resp = Mock()
        mock_resp.text = "<html><body><h1>Sin meta</h1></body></html>"
        with patch.object(mod, "retry_request", return_value=mock_resp):
            assert fetch_rayados_detail("https://www.rayados.com/es/noticias/1/x/") == (None, None)

    def test_error_retorna_nones(self):
        with patch.object(mod, "retry_request", side_effect=Exception("timeout")):
            assert fetch_rayados_detail("https://www.rayados.com/es/noticias/1/x/") == (None, None)

    def test_enrich_respeta_tope(self):
        items = [
            NewsItem(
                title=f"Nota oficial suficientemente larga {i}",
                link=f"https://www.rayados.com/es/noticias/{i}/x/",
                source="rayados.com",
                oficial=True,
            )
            for i in range(3)
        ]
        mock_resp = Mock()
        mock_resp.text = RAYADOS_DETAIL_HTML
        with patch.object(mod, "retry_request", return_value=mock_resp) as mock_req:
            enrich_rayados_items(items, max_details=2)
            assert mock_req.call_count == 2
            assert items[0].author == "Prensa Rayados"
            assert items[2].author is None


class TestFormatItemLine:
    def test_con_fecha_y_autor(self):
        from datetime import datetime, timezone

        item = NewsItem(
            title="Ganan las Rayadas en Guadalajara - rayados.com",
            source="rayados.com",
            published=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
            author="Prensa Rayados",
        )
        line = format_item_line(
            "🎽",
            item,
            "https://news.google.com/rss/articles/CBMiW2h0dHBzOi8vZXhhbXBsZS5jb20vbm90YS1sYXJnYS1jb24tdXJsLW11eS1sYXJnYS1wYXJhLXByb2Jhci1lbC1hbGlhcy1tYXJrZG93btIBX2h0dHBzOi8vZXhhbXBsZS5jb20vbm90YQ?oc=5",
        )
        assert "(2026-09-14)" in line
        assert "por Prensa Rayados" in line
        assert "[Ganan las Rayadas en Guadalajara]" in line
        assert "https://news.google.com/rss/articles/" in line

    def test_sin_fecha_no_muestra_parentesis(self):
        item = NewsItem(title="Nota sin fecha", source="rayados.com")
        line = format_item_line("🎽", item, "")
        assert "(" not in line
        assert "Nota sin fecha" in line


class TestVersionEnEncabezado:
    def test_header_trae_version(self):
        """El bloque 0 incluye _hermes-scripts <tag> (issue #91)."""
        with (
            patch("hermes_common.HistoryManager") as mock_hist_cls,
            patch.object(mod, "fetch_google_news", return_value=[]),
            patch.object(mod, "fetch_rayados_com", return_value=[]),
        ):
            mock_hist_cls.return_value.exists.return_value = False
            blocks = mod.build_report_blocks()
        assert any(line.startswith("_hermes-scripts ") for line in blocks[0].splitlines())
