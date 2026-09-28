"""Tests para src/hermes_common/news_utils.py (issue #70)."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from hermes_common import news_utils

NewsItem = news_utils.NewsItem

# Edición que declaran los reportes de equipos mexicanos (ADR 0010): dato del reporte, no default.
EDICION_MX = {"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"}


class TestCleanUrl:
    def test_limpia_tracking(self):
        url = "https://news.google.com/rss/articles/CBMi?oc=5&utm_source=x&ceid=MX:es-419"
        result = news_utils.clean_url(url)
        assert "oc=" not in result
        assert "utm_" not in result
        assert "ceid=" not in result

    def test_escape_parens_opcional(self):
        url = "https://example.com/nota_(1)"
        assert news_utils.clean_url(url).endswith(")")
        assert news_utils.clean_url(url, escape_parens=True).endswith("%29")

    def test_url_limpia_sin_cambio(self):
        url = "https://example.com/clean/article"
        assert news_utils.clean_url(url) == url


class TestCleanTitle:
    def test_remueve_source_suffix(self):
        assert news_utils.clean_title("Tigres ficha a crack - ESPN") == "Tigres ficha a crack"

    def test_escapa_brackets(self):
        assert news_utils.clean_title("Elon [Musk] speaks") == "Elon (Musk) speaks"

    def test_vacio(self):
        assert news_utils.clean_title("") == ""


class TestCanonicalTitle:
    def test_normaliza(self):
        assert news_utils.canonical_title("Rayados GANA 2 0!!") == "rayadosgana20"

    def test_vacio(self):
        assert news_utils.canonical_title("") == ""
        assert news_utils.canonical_title("!!!") == ""


class TestTitleSimilar:
    def test_identicos(self):
        assert news_utils.title_similar("Tigres ficha crack", "Tigres ficha crack") is True

    def test_diferentes(self):
        assert (
            news_utils.title_similar("Tigres gana el clásico", "Rayados anuncia nuevo estadio")
            is False
        )

    def test_vacios(self):
        assert news_utils.title_similar("", "Tigres") is False
        assert news_utils.title_similar("", "") is False


class TestDedupeByTitle:
    def test_exactos_colapsan_por_hash(self):
        items = [
            NewsItem(title="Rayados gana 2-0"),
            NewsItem(title="Rayados GANA 2 0!!"),
            NewsItem(title="Otra noticia"),
        ]
        result = news_utils.dedupe_by_title(items)
        assert [i.title for i in result] == ["Rayados gana 2-0", "Otra noticia"]

    def test_threshold_1_solo_exactos(self):
        items = [
            NewsItem(title="Noticia original"),
            NewsItem(title="Noticia original (copia)"),
            NewsItem(title="Noticia original"),
        ]
        result = news_utils.dedupe_by_title(items, threshold=1.0)
        assert [i.title for i in result] == ["Noticia original", "Noticia original (copia)"]

    def test_comparaciones_acotadas(self, monkeypatch):
        calls = {"n": 0}
        real = news_utils.title_similar

        def counting(t1, t2, threshold=0.85):
            calls["n"] += 1
            return real(t1, t2, threshold)

        monkeypatch.setattr(news_utils, "title_similar", counting)
        items = [NewsItem(title=f"Asunto-{i:04d}-abc relleno dedupe") for i in range(200)]
        result = news_utils.dedupe_by_title(items)
        assert len(result) == 200
        assert calls["n"] < 1000


class TestDedupe:
    def test_por_link(self):
        items = [
            NewsItem(title="Noticia 1", link="https://a.com/1"),
            NewsItem(title="Noticia 1 dup", link="https://a.com/1"),
            NewsItem(title="Noticia 2", link="https://a.com/2"),
        ]
        assert len(news_utils.dedupe(items)) == 2


class TestDomainHelpers:
    OFICIALES = ["tigres.com.mx"]
    CONFIABLES = ["espn.com.mx"]

    def test_is_oficial(self):
        assert news_utils.is_oficial("https://www.tigres.com.mx/es/noticias/x/", self.OFICIALES)
        assert not news_utils.is_oficial("https://espn.com.mx/x", self.OFICIALES)

    def test_is_confiable(self):
        assert news_utils.is_confiable(
            "ESPN", "https://espn.com.mx/x", self.OFICIALES, self.CONFIABLES
        )
        assert not news_utils.is_confiable(
            "Blog", "https://blog.com/x", self.OFICIALES, self.CONFIABLES
        )

    def test_smells_like_rumor(self):
        assert news_utils.smells_like_rumor("Rumor: fichaje cerca", ["rumor", "fichaje"])
        assert not news_utils.smells_like_rumor("Comunicado oficial", ["rumor", "fichaje"])


class TestParseFechaEs:
    def test_mes_dia_ano(self):
        got = news_utils.parse_fecha_es("septiembre 12, 2026")
        assert got is not None
        assert (got.year, got.month, got.day) == (2026, 9, 12)

    def test_dia_de_mes_de_ano(self):
        got = news_utils.parse_fecha_es("5 de septiembre de 2026")
        assert got is not None
        assert (got.year, got.month, got.day) == (2026, 9, 5)

    def test_invalido(self):
        assert news_utils.parse_fecha_es("") is None
        assert news_utils.parse_fecha_es("ayer en la tarde") is None


class TestParseDetailPage:
    HTML = """
    <html><head>
    <meta property="article:published_time" content="2026-09-12T15:22:23+00:00" />
    <meta name="author" content="Ernesto Ramos" />
    </head><body><h1>Nota</h1></body></html>
    """

    def test_fecha_y_autor(self):
        published, author = news_utils.parse_detail_page(self.HTML)
        assert published is not None
        assert (published.year, published.month, published.day) == (2026, 9, 12)
        assert author == "Ernesto Ramos"

    def test_sin_tags(self):
        assert news_utils.parse_detail_page("<html><body><h1>X</h1></body></html>") == (None, None)


class TestEnrichFromDetail:
    def test_completa_y_respeta_tope(self):
        items = [NewsItem(title=f"Nota {i}", link=f"https://club.mx/{i}/") for i in range(3)]

        def fake_detail(link):
            return datetime(2026, 9, 12, tzinfo=timezone.utc), "Redacción"

        news_utils.enrich_from_detail(items, fake_detail, max_details=2)
        assert items[0].author == "Redacción"
        assert items[0].published.day == 12
        assert items[2].author is None
        assert items[2].published is None


class TestFormatItemLine:
    def test_con_fecha_y_autor(self):
        item = NewsItem(
            title="La Previa - tigres.com.mx",
            source="tigres.com.mx",
            published=datetime(2026, 9, 12, 15, 22, tzinfo=timezone.utc),
            author="Ernesto Ramos",
        )
        line = news_utils.format_item_line(
            "🎽",
            item,
            "https://news.google.com/rss/articles/CBMiW2h0dHBzOi8vZXhhbXBsZS5jb20vbm90YS1sYXJnYS1jb24tdXJsLW11eS1sYXJnYS1wYXJhLXByb2Jhci1lbC1hbGlhcy1tYXJrZG93btIBX2h0dHBzOi8vZXhhbXBsZS5jb20vbm90YQ?oc=5",
        )
        assert "(2026-09-12)" in line
        assert "por Ernesto Ramos" in line
        assert "https://news.google.com/rss/articles/" in line

    def test_sin_fecha(self):
        item = NewsItem(title="Nota sin fecha", source="Medio")
        line = news_utils.format_item_line("✓", item, "")
        assert "(" not in line


class TestFetchGoogleNews:
    def test_error_retorna_item(self):
        with patch("feedparser.parse", side_effect=Exception("timeout")):
            items = news_utils.fetch_google_news(
                "q", "confirmadas", ["a.com"], ["b.com"], ["rumor"], EDICION_MX
            )
            assert len(items) == 1
            assert items[0].title.startswith("[Error Google News")

    def test_parse_rss(self):
        entry = Mock()
        entry.get.side_effect = lambda k, d="": {
            "title": "Nota - ESPN",
            "link": "https://espn.com.mx/x",
            "author": "ESPN",
        }.get(k, d)
        entry.source = {"title": "ESPN"}
        mock_feed = Mock(entries=[entry])
        with patch("feedparser.parse", return_value=mock_feed):
            items = news_utils.fetch_google_news(
                "q", "confirmadas", ["tigres.com.mx"], ["espn.com.mx"], ["rumor"], EDICION_MX
            )
            assert len(items) == 1
            assert items[0].source == "ESPN"
            assert items[0].confiable is True


class TestClassify:
    def test_oficial_a_confirmadas(self):
        items = [
            NewsItem(
                title="Oficial",
                link="https://tigres.com.mx/x/",
                source="tigres.com.mx",
                oficial=True,
                confiable=True,
                origin="tigres.com.mx",
                category="confirmadas",
            )
        ]
        conf, rum = news_utils.classify(items, ["tigres.com.mx"], ["espn.com.mx"])
        assert len(conf) == 1
        assert rum == []


class TestEdicionDelFeed:
    """La edición del feed se declara por reporte (ADR 0010, issue #357)."""

    def test_la_edicion_declarada_da_la_url_de_siempre(self):
        """Los reportes vivos declaran la mexicana en su config: su URL es la de antes."""
        url = news_utils.build_google_news_url("Tigres", EDICION_MX)
        assert url == "https://news.google.com/rss/search?q=Tigres&hl=es-419&gl=MX&ceid=MX:es-419"

    def test_sin_edicion_no_hay_url(self):
        """Sin edición declarada no se arma URL: no hay herencia por omisión (ADR 0010)."""
        with pytest.raises(TypeError):
            news_utils.build_google_news_url("Tigres")  # type: ignore[call-arg]

    def test_edicion_explicita_cambia_hl_gl_ceid(self):
        en_eeuu = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
        url = news_utils.build_google_news_url("Titans", en_eeuu)
        assert url.endswith("&hl=en-US&gl=US&ceid=US:en")
        assert "es-419" not in url

    def test_la_edicion_llega_al_feed(self):
        capturado = {}

        def falso_parse(url):
            capturado["url"] = url
            return Mock(entries=[])

        with patch("feedparser.parse", side_effect=falso_parse):
            news_utils.fetch_google_news(
                "Titans",
                "confirmadas",
                ["tennesseetitans.com"],
                ["espn.com"],
                ["rumor"],
                {"hl": "en-US", "gl": "US", "ceid": "US:en"},
            )
        assert capturado["url"].endswith("&hl=en-US&gl=US&ceid=US:en")

    def test_el_feed_exige_la_edicion(self):
        """`fetch_google_news` sin edición tampoco arranca: el olvido se ve, no se hereda."""
        with pytest.raises(TypeError):
            news_utils.fetch_google_news(  # type: ignore[call-arg]
                "Tigres", "confirmadas", ["tigres.com.mx"], [], ["rumor"]
            )

    def test_el_feed_sale_en_la_edicion_declarada(self):
        capturado = {}

        def falso_parse(url):
            capturado["url"] = url
            return Mock(entries=[])

        with patch("feedparser.parse", side_effect=falso_parse):
            news_utils.fetch_google_news(
                "Tigres", "confirmadas", ["tigres.com.mx"], [], ["rumor"], EDICION_MX
            )
        assert capturado["url"].endswith("&hl=es-419&gl=MX&ceid=MX:es-419")


# dedupe por historia (#386)


def _nota(titulo: str, *, fuente: str = "Medio", oficial=False, confiable=False) -> NewsItem:
    return NewsItem(
        title=titulo,
        link=f"https://ejemplo.com/{abs(hash(titulo))}",
        source=fuente,
        oficial=oficial,
        confiable=confiable,
        origin="gn",
        category="confirmadas",
    )


class TestStoryTokens:
    def test_quita_relleno_y_palabras_cortas(self):
        assert news_utils.story_tokens("What we learned from the NFL news of the Titans") == {
            "learned",
            "titans",
        }

    def test_titulo_vacio(self):
        assert news_utils.story_tokens("") == set()


class TestStorySimilar:
    def test_el_mismo_partido_contado_por_dos_medios(self):
        a = news_utils.story_tokens(
            "What we learned from Tennessee Titans' 12-7 loss to New York Giants"
        )
        b = news_utils.story_tokens("What we learned from New York Giants' 12-7 win over Titans")
        assert news_utils.story_similar(a, b)

    def test_dos_noticias_distintas_del_mismo_equipo(self):
        a = news_utils.story_tokens(
            "Titans face offensive line injury concerns heading into Week 4"
        )
        b = news_utils.story_tokens("Titans open as 11-point underdogs vs. Ravens in Week 4")
        assert not news_utils.story_similar(a, b)

    def test_sin_palabras_no_hay_historia(self):
        assert not news_utils.story_similar(set(), set())


class TestDedupeByStory:
    def test_colapsa_el_partido_cubierto_por_tres_medios(self):
        items = [
            _nota("What we learned from Tennessee Titans' 12-7 loss to New York Giants"),
            _nota("🎥 Highlights: New York Giants 12, Tennessee Titans 7"),
            _nota("What we learned from New York Giants' 12-7 win over Tennessee Titans"),
        ]
        assert len(news_utils.dedupe_by_story(items)) == 1

    def test_deja_en_pie_el_mismo_partido_contado_desde_otro_angulo(self):
        """Medido en #386: el análisis del ataque no es la misma nota que el resumen.

        Con cifras en las palabras (medido hoy) este ángulo se queda: fusionarlo
        era perder información, que es justo lo que el operador reportó.
        """
        items = [
            _nota("What we learned from Tennessee Titans' 12-7 loss to New York Giants"),
            _nota("What we learned from New York Giants' 12-7 win over Tennessee Titans"),
            _nota("Tennessee Titans' offense stalls in loss to New York Giants in Week 3"),
        ]
        assert len(news_utils.dedupe_by_story(items)) == 2

    def test_no_se_traga_el_angulo_distinto(self):
        """Medido en #386: a 0.45-0.50 este ángulo se lo comía el grupo del partido."""
        items = [
            _nota("What we learned from Tennessee Titans' 12-7 loss to New York Giants"),
            _nota("What we learned from New York Giants' 12-7 win over Tennessee Titans"),
            _nota("Tennessee Titans QB Cam Ward talks about late INT vs. New York Giants"),
        ]
        quedan = news_utils.dedupe_by_story(items)
        assert len(quedan) == 2
        assert any("late INT" in i.title for i in quedan)

    def test_conserva_la_fuente_de_mejor_rango(self):
        """El medio confiable le gana al desconocido, aunque llegue después."""
        items = [
            _nota("NY Giants beat Tennessee Titans 12-7 -- but lose Brian Burns to knee injury"),
            _nota(
                "Giants hold on to beat the Titans 12-7 but lose Brian Burns to a knee injury",
                fuente="ABC News",
                confiable=True,
            ),
        ]
        quedan = news_utils.dedupe_by_story(items)
        assert len(quedan) == 1
        assert quedan[0].source == "ABC News"

    def test_lo_oficial_le_gana_al_medio_confiable(self):
        items = [
            _nota("Jeffery Simmons Press Conference Titans", confiable=True),
            _nota("Jeffery Simmons Press Conference Titans", oficial=True, fuente="Titans"),
        ]
        quedan = news_utils.dedupe_by_story(items)
        assert len(quedan) == 1
        assert quedan[0].source == "Titans"

    def test_respeta_el_orden_de_la_primera_aparicion(self):
        items = [
            _nota("Titans open as 11-point underdogs vs. Ravens in Week 4"),
            _nota("What we learned from Tennessee Titans' 12-7 loss to New York Giants"),
            _nota("What we learned from New York Giants' 12-7 win over Titans"),
            _nota("Titans stock report after Week 3 loss"),
        ]
        quedan = news_utils.dedupe_by_story(items)
        assert quedan[0].title.startswith("Titans open as")
        assert len(quedan) == 3

    def test_los_titulares_sin_palabras_significativas_no_se_juntan(self):
        items = [_nota("12-7"), _nota("3-2"), _nota("NFL 24")]
        assert len(news_utils.dedupe_by_story(items)) == 3

    def test_lista_vacia(self):
        assert news_utils.dedupe_by_story([]) == []


# feeds RSS directos (#386)


class TestFetchRssFeed:
    def test_items_con_su_fuente_y_su_categoria(self):
        entradas = [
            {
                "title": "Dolphins RB De'Von Achane out for season",
                "link": "https://www.cbssports.com/nfl/news/achane",
                "published_parsed": None,
            }
        ]
        with patch("feedparser.parse", return_value=Mock(entries=entradas)):
            items = news_utils.fetch_rss_feed(
                "https://www.cbssports.com/rss/headlines/nfl/",
                "CBS Sports",
                "liga",
                [],
                ["cbssports.com"],
                ["rumor"],
            )
        assert len(items) == 1
        assert items[0].source == "CBS Sports"
        assert items[0].origin == "rss:CBS Sports"
        assert items[0].category == "liga"
        assert items[0].confiable is True
        assert items[0].link == "https://www.cbssports.com/nfl/news/achane"

    def test_sin_titulo_o_sin_enlace_se_descarta(self):
        entradas = [{"title": "", "link": "https://x/1"}, {"title": "Sin enlace", "link": ""}]
        with patch("feedparser.parse", return_value=Mock(entries=entradas)):
            assert news_utils.fetch_rss_feed("https://x", "FOX", "liga", [], [], []) == []

    def test_un_feed_caido_no_tumba_el_reporte(self):
        with patch("feedparser.parse", side_effect=RuntimeError("boom")):
            items = news_utils.fetch_rss_feed("https://x", "FOX Sports", "liga", [], [], [])
        assert len(items) == 1
        assert items[0].title.startswith("[Error feed FOX Sports (liga)")
        assert items[0].category == "liga"

    def test_el_tope_de_items_es_configurable(self):
        entradas = [
            {"title": f"Asunto {i}", "link": f"https://x/{i}", "published_parsed": None}
            for i in range(30)
        ]
        with patch("feedparser.parse", return_value=Mock(entries=entradas)):
            items = news_utils.fetch_rss_feed("https://x", "FOX", "liga", [], [], [], limit=5)
        assert len(items) == 5
