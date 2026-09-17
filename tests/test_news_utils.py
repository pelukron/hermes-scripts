"""Tests para src/hermes_common/news_utils.py (issue #70)."""

import sys
from datetime import datetime, timezone
from unittest.mock import Mock, patch

sys.path.insert(0, ".")
from hermes_common import news_utils

NewsItem = news_utils.NewsItem


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
                "q", "confirmadas", ["a.com"], ["b.com"], ["rumor"]
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
                "q", "confirmadas", ["tigres.com.mx"], ["espn.com.mx"], ["rumor"]
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
