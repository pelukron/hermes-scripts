"""Tests para funciones clave de resumen-tigres-diario.py"""

import importlib.util
import os
import re
from unittest.mock import Mock, patch

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "resumen_tigres",
    os.path.join(SCRIPT_DIR, "src", "scripts", "resumen_tigres_diario.py"),
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
fetch_google_news = mod.fetch_google_news
fetch_tigres_com = mod.fetch_tigres_com
parse_fecha_es = mod.parse_fecha_es
fetch_tigres_detail = mod.fetch_tigres_detail
enrich_tigres_items = mod.enrich_tigres_items
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
        assert clean_title("Tigres ficha a crack - ESPN") == "Tigres ficha a crack"

    def test_multiples_dashes_solo_primer_corte(self):
        assert clean_title("Tigres - Rayados - Clásico Regio - Mediotiempo") == "Tigres"

    def test_reemplaza_brackets(self):
        assert (
            clean_title("[OFICIAL] Tigres anuncia refuerzo") == "(OFICIAL) Tigres anuncia refuerzo"
        )

    def test_sin_suffix_sin_cambio(self):
        assert clean_title("Tigres gana el clásico") == "Tigres gana el clásico"

    def test_titulo_vacio(self):
        assert clean_title("") == ""


# ═══════════════════════════════════════════
# title_similar
# ═══════════════════════════════════════════


class TestTitleSimilar:
    def test_titulos_identicos(self):
        assert title_similar("Tigres ficha crack", "Tigres ficha crack") is True

    def test_titulos_muy_similares(self):
        assert (
            title_similar(
                "Tigres ficha a crack mundial",
                "Tigres ficha a crack mundial",
            )
            is True
        )

    def test_titulos_diferentes(self):
        assert (
            title_similar(
                "Tigres gana el clásico",
                "Rayados anuncia nuevo estadio",
            )
            is False
        )

    def test_titulos_vacios(self):
        assert title_similar("", "Tigres") is False
        assert title_similar("Tigres", "") is False
        assert title_similar("", "") is False

    def test_threshold_personalizado(self):
        # Títulos similares pero con diferencia notable
        t1 = "Tigres ficha a Carlos Vela por 5 millones"
        t2 = "Tigres ficha a Carlos Vela por 10 millones"
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
            NewsItem(title="Tigres ficha a crack mundial"),
            NewsItem(title="Tigres Ficha A Crack Mundial!!"),
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
# domain_of
# ═══════════════════════════════════════════


class TestDomainOf:
    def test_extrae_dominio(self):
        assert domain_of("https://tigres.com.mx/es/noticias") == "tigres.com.mx"

    def test_ignora_www(self):
        assert domain_of("https://www.espn.com.mx/rayados") == "espn.com.mx"

    def test_ignora_protocolo_http(self):
        assert domain_of("http://mediotiempo.com/nota") == "mediotiempo.com"


# ═══════════════════════════════════════════
# is_oficial
# ═══════════════════════════════════════════


class TestIsOficial:
    def test_url_oficial(self):
        assert is_oficial("https://www.tigres.com.mx/es/noticias/x/") is True

    def test_url_no_oficial(self):
        assert is_oficial("https://espn.com.mx/tigres") is False


# ═══════════════════════════════════════════
# smells_like_rumor
# ═══════════════════════════════════════════


class TestSmellsLikeRumor:
    def test_detecta_rumor_explicito(self):
        assert smells_like_rumor("Rumor: Tigres busca fichaje bomba") is True

    def test_detecta_filtracion(self):
        assert smells_like_rumor("Filtran posible refuerzo de Tigres") is True

    def test_detecta_fichaje(self):
        assert smells_like_rumor("Tigres anuncia fichaje millonario") is True

    def test_titulo_objetivo_sin_rumor(self):
        assert smells_like_rumor("Tigres gana 3-0 al América") is False

    def test_case_insensitive(self):
        assert smells_like_rumor("RUMOR: Tigres ficha a Messi") is True


# ═══════════════════════════════════════════
# classify
# ═══════════════════════════════════════════


class TestClassify:
    def test_oficial_va_a_confirmadas(self):
        items = [
            NewsItem(
                title="Noticia oficial",
                link="https://www.tigres.com.mx/es/noticia/",
                source="tigres.com.mx",
                oficial=True,
                confiable=True,
                origin="tigres.com.mx",
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
                title="[Error tigres.com.mx: timeout]",
                source="tigres.com.mx",
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
                title="Tigres gana",
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
                title="Tigres anuncia nuevo patrocinador",
                link="https://blograndom.com/tigres",
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
        title="Tigres gana 3-0 al América",
        link="https://news.google.com/rss/articles/1?oc=5",
        source=Mock(title="ESPN"),
        author="ESPN",
    ),
    Mock(
        title="Rumor: Tigres busca fichaje estrella - Mediotiempo",
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
            items = fetch_google_news("Tigres", "confirmadas")
            assert len(items) == 1
            item = items[0]
            assert "Tigres" in item.title
            assert item.origin == "google-news"
            assert item.category == "confirmadas"

    def test_detecta_oficial(self):
        mock_feed = Mock()
        source_mock = Mock(title="tigres.com.mx")
        source_mock.get = lambda key, default="", _s=source_mock: getattr(_s, key, default)
        entry_oficial = Mock(
            title="Noticia oficial",
            link="https://www.tigres.com.mx/es/noticias/123/",
            source=source_mock,
            author="tigres.com.mx",
        )
        entry_oficial.get = lambda key, default="", _e=entry_oficial: getattr(_e, key, default)
        mock_feed.entries = [entry_oficial]
        with patch.object(mod.feedparser, "parse", return_value=mock_feed):
            items = fetch_google_news("Tigres", "confirmadas")
            assert len(items) == 1
            assert items[0].oficial is True

    def test_excepcion_retorna_error_item(self):
        with patch.object(mod.feedparser, "parse", side_effect=Exception("timeout")):
            items = fetch_google_news("Tigres", "confirmadas")
            assert len(items) == 1
            assert items[0].title.startswith("[Error")


# ═══════════════════════════════════════════
# fetch_tigres_com
# ═══════════════════════════════════════════

TIGRES_HTML = """
<html><body>
<a href="https://www.tigres.com.mx/es/noticias/tigres/"></a>
<a href="https://www.tigres.com.mx/es/noticias/comunicado-oficial-victor-manuel-vucetich/">
  <h2>Comunicado Oficial, Víctor Manuel Vucetich.</h2></a>
<a href="https://www.tigres.com.mx/es/noticias/la-previa-sportiumbet-tigres-vs-santos-2/">
  <h3>La Previa SportiumBet Tigres vs. Santos</h3></a>
<a href="https://www.tigres.com.mx/es/noticias/"></a>
</body></html>
"""


class TestFetchTigresCom:
    def test_parse_html_exitoso(self):
        mock_resp = Mock()
        mock_resp.text = TIGRES_HTML
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_tigres_com()
            assert len(items) == 2
            assert items[0].title == "Comunicado Oficial, Víctor Manuel Vucetich."
            assert items[0].source == "tigres.com.mx"
            assert items[0].oficial is True
            assert "tigres.com.mx/es/noticias/comunicado-oficial" in items[0].link

    def test_excepcion_retorna_error_item(self):
        with patch.object(
            mod,
            "retry_request",
            side_effect=Exception("Connection refused"),
        ):
            items = fetch_tigres_com()
            assert len(items) == 1
            assert items[0].title.startswith("[Error tigres.com.mx")

    def test_items_sin_heading_usan_title_attr(self):
        html = """
        <html><body>
        <a href="https://www.tigres.com.mx/es/noticias/dummy-slug/"
           title="Título desde atributo title"></a>
        </body></html>
        """
        mock_resp = Mock()
        mock_resp.text = html
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_tigres_com()
            assert len(items) == 1
            assert items[0].title == "Título desde atributo title"

    def test_titulos_cortos_ignorados(self):
        """Títulos con menos de 10 caracteres se ignoran."""
        html = """
        <html><body>
        <a href="https://www.tigres.com.mx/es/noticias/slug-uno/"><h2>Corto</h2></a>
        <a href="https://www.tigres.com.mx/es/noticias/slug-dos/">
          <h2>Este título sí es suficientemente largo</h2></a>
        </body></html>
        """
        mock_resp = Mock()
        mock_resp.text = html
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_tigres_com()
            assert len(items) == 1


# ═══════════════════════════════════════════
# Queries de Google News (BUG 1)
# ═══════════════════════════════════════════


def test_queries_usan_frases_entre_comillas():
    """La query debe abrir con una frase entre comillas; OR o termino suelto tras ella."""
    # Patrón: la query abre con frase citada y luego solo or-frases citadas o terminos sueltos
    # (sin AND explicito, sin parentesis, sin operar solo con terminos sueltos).
    patron = r'^"[^"]+"(?:\s+OR\s+"[^"]+"|\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+)*$'
    for key, q in mod.QUERIES.items():
        assert re.fullmatch(patron, q), f"QUERIES[{key}] no cumple sintaxis: {q}"
        assert "(" not in q and ")" not in q, f"QUERIES[{key}] usa parentesis: {q}"
        assert " AND " not in q, f"QUERIES[{key}] usa AND explicito: {q}"


def test_queries_no_usan_operador_and_explicito():
    """Google News RSS devuelve 0 entries si la query usa AND o parentesis."""
    for key, q in mod.QUERIES.items():
        assert " AND " not in q, f"QUERIES[{key}] usa AND explicito: {q}"
        assert "(" not in q, f"QUERIES[{key}] usa parentesis: {q}"


# ═══════════════════════════════════════════
# Contador de sección (BUG 2)
# ═══════════════════════════════════════════


def _mk_confirmada(i: int) -> NewsItem:
    return NewsItem(
        title=f"Nota {i}",
        link=f"https://ejemplo.com/{i}",
        source="Medio",
        confiable=True,
        origin="gn",
        category="confirmadas",
    )


def test_contador_refleja_items_mostrados():
    """Con 12 confirmadas y limite 8, el header debe decir '8 de 12' (o 8)."""
    confirmadas = [_mk_confirmada(i) for i in range(12)]
    with (
        patch("hermes_common.HistoryManager") as mock_hist_cls,
        patch.object(mod, "fetch_google_news") as mock_gn,
        patch.object(mod, "fetch_tigres_com") as mock_tig,
    ):
        mock_hist_cls.return_value.exists.return_value = False
        mock_gn.side_effect = lambda q, cat: confirmadas if cat == "confirmadas" else []
        mock_tig.return_value = []
        blocks = mod.build_report_blocks()

    conf = [b for b in blocks if "CONFIRMADO" in b][0]
    bullets = [line for line in conf.splitlines() if line.startswith("- ")]
    header = conf.splitlines()[0]
    assert str(len(bullets)) in header, f"header {header!r} no coincide con {len(bullets)} bullets"
    assert len(bullets) <= 8
    # Hubo recorte (12 originales > 8): el header debe indicar el total
    assert " de " in header, f"header {header!r} deberia indicar el total recortado"


# ═══════════════════════════════════════════
# Fecha del listado en español (issue #124)
# ═══════════════════════════════════════════


class TestParseFechaEs:
    def test_mes_dia_ano(self):
        got = parse_fecha_es("septiembre 12, 2026")
        assert got is not None
        assert (got.year, got.month, got.day) == (2026, 9, 12)

    def test_dia_de_mes_de_ano(self):
        got = parse_fecha_es("5 de septiembre de 2026")
        assert got is not None
        assert (got.year, got.month, got.day) == (2026, 9, 5)

    def test_agosto(self):
        got = parse_fecha_es("agosto 29, 2026")
        assert got is not None
        assert (got.year, got.month, got.day) == (2026, 8, 29)

    def test_invalido(self):
        assert parse_fecha_es("") is None
        assert parse_fecha_es("ayer en la tarde") is None


TIGRES_HTML_CON_FECHA = """
<html><body>
<div class="card"><time>septiembre 12, 2026</time>
<a href="https://www.tigres.com.mx/es/noticias/nota-reciente-x/">
<h2>Nota reciente con fecha del listado</h2></a></div>
<div class="card"><time>agosto 21, 2026</time>
<a href="https://www.tigres.com.mx/es/noticias/nota-vieja-zzz/">
<h2>Nota vieja de agosto del listado</h2></a></div>
</body></html>
"""


class TestFetchTigresComConFecha:
    def test_listado_aporta_published(self):
        mock_resp = Mock()
        mock_resp.text = TIGRES_HTML_CON_FECHA
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_tigres_com()
            assert len(items) == 2
            assert items[0].published is not None
            assert (items[0].published.year, items[0].published.month) == (2026, 9)
            assert (items[1].published.year, items[1].published.month) == (2026, 8)

    def test_filtro_48h_descarta_agosto(self):
        from datetime import datetime, timezone

        from hermes_common import filter_by_max_age

        now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
        mock_resp = Mock()
        mock_resp.text = TIGRES_HTML_CON_FECHA
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_tigres_com()
            kept = filter_by_max_age(items, missing="drop", now=now)
            assert len(kept) == 1
            assert "reciente" in kept[0].title.lower()

    def test_sin_fecha_se_descarta_con_drop(self):
        from hermes_common import filter_by_max_age

        mock_resp = Mock()
        mock_resp.text = TIGRES_HTML
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_tigres_com()
            assert all(i.published is None for i in items)
            assert filter_by_max_age(items, missing="drop") == []


TIGRES_DETAIL_HTML = """
<html><head>
<meta property="article:published_time" content="2026-09-12T15:22:23+00:00" />
<meta name="author" content="Ernesto Ramos" />
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Article",
 "datePublished": "2026-09-12T15:22:23+00:00",
 "author": {"name": "Ernesto Ramos"}}
</script>
</head><body><h1>Nota</h1></body></html>
"""


class TestFetchTigresDetail:
    def test_fecha_y_autor(self):
        mock_resp = Mock()
        mock_resp.text = TIGRES_DETAIL_HTML
        with patch.object(mod, "retry_request", return_value=mock_resp):
            published, author = fetch_tigres_detail("https://www.tigres.com.mx/es/noticias/x/")
            assert published is not None
            assert (published.year, published.month, published.day) == (2026, 9, 12)
            assert author == "Ernesto Ramos"

    def test_error_retorna_nones(self):
        with patch.object(mod, "retry_request", side_effect=Exception("timeout")):
            assert fetch_tigres_detail("https://www.tigres.com.mx/es/noticias/x/") == (None, None)

    def test_enrich_respeta_tope_y_completa(self):
        from datetime import datetime, timezone

        items = [
            NewsItem(
                title="Nota reciente con fecha del listado",
                link="https://www.tigres.com.mx/es/noticias/a/",
                source="tigres.com.mx",
                oficial=True,
                published=datetime(2026, 9, 12, tzinfo=timezone.utc),
            ),
            NewsItem(
                title="Otra nota reciente del listado",
                link="https://www.tigres.com.mx/es/noticias/b/",
                source="tigres.com.mx",
                oficial=True,
                published=datetime(2026, 9, 13, tzinfo=timezone.utc),
            ),
        ]
        mock_resp = Mock()
        mock_resp.text = TIGRES_DETAIL_HTML
        with patch.object(mod, "retry_request", return_value=mock_resp) as mock_req:
            enrich_tigres_items(items, max_details=1)
            assert mock_req.call_count == 1
            assert items[0].author == "Ernesto Ramos"
            assert items[1].author is None


class TestFormatItemLine:
    def test_con_fecha_y_autor(self):
        from datetime import datetime, timezone

        item = NewsItem(
            title="La Previa Tigres vs Rayados - tigres.com.mx",
            source="tigres.com.mx",
            published=datetime(2026, 9, 12, 15, 22, tzinfo=timezone.utc),
            author="Ernesto Ramos",
        )
        line = format_item_line(
            "🎽",
            item,
            "https://news.google.com/rss/articles/CBMiW2h0dHBzOi8vZXhhbXBsZS5jb20vbm90YS1sYXJnYS1jb24tdXJsLW11eS1sYXJnYS1wYXJhLXByb2Jhci1lbC1hbGlhcy1tYXJrZG93btIBX2h0dHBzOi8vZXhhbXBsZS5jb20vbm90YQ?oc=5",
        )
        assert "(2026-09-12)" in line
        assert "por Ernesto Ramos" in line
        assert "[La Previa Tigres vs Rayados]" in line
        assert "https://news.google.com/rss/articles/" in line

    def test_sin_fecha_no_muestra_parentesis(self):
        item = NewsItem(title="Nota sin fecha", source="Medio")
        line = format_item_line("✓", item, "")
        assert "(" not in line
        assert "Nota sin fecha" in line


class TestVersionEnEncabezado:
    def test_header_trae_version(self):
        """El bloque 0 incluye *hermes-scripts <tag> (issue #91)."""
        with (
            patch("hermes_common.HistoryManager") as mock_hist_cls,
            patch.object(mod, "fetch_google_news", return_value=[]),
            patch.object(mod, "fetch_tigres_com", return_value=[]),
        ):
            mock_hist_cls.return_value.exists.return_value = False
            blocks = mod.build_report_blocks()
        assert any(line.startswith("*hermes-scripts ") for line in blocks[0].splitlines())
