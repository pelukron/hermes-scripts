"""Tests para funciones clave de resumen-noticias-diario.py"""

import importlib.util  # noqa: E402
import os
import sys
import threading
from unittest.mock import Mock, patch

# Add script dir to path para importar
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

# Import functions under test
# Usamos import directo del script (sin .py)

spec = importlib.util.spec_from_file_location(
    "resumen_noticias",
    os.path.join(SCRIPT_DIR, "src", "scripts", "resumen_noticias_diario.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

clean_title = mod.clean_title
escape_link = mod.escape_link
fetch_rss = mod.fetch_rss
fetch_all_rss = mod.fetch_all_rss

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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 4  # max 4 items
            assert items[0] == ("First Article Title", "https://example.com/first")
            assert items[1] == ("Second Article", "https://example.com/second")

    def test_filtra_boilerplate_google_news(self):
        """Ignora títulos que empiezan con \" y contienen ' when:'"""
        mock_resp = Mock()
        mock_resp.content = GN_BOILERPLATE_XML.encode("utf-8")
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 2
            assert items[0] == ("RDF Article One", "https://example.com/rdf/1")
            assert items[1] == ("RDF Article Two", "https://example.com/rdf/2")

    def test_excepcion_retorna_lista_vacia(self):
        """Cualquier excepción → []"""
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", side_effect=Exception("boom")):
            items = fetch_rss(self.URL)
            assert items == []

    def test_xml_malformado(self):
        """XML inválido → []"""

        mock_resp = Mock()
        mock_resp.content = b"not valid xml <<<"
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
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
        with patch("src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp):
            items = fetch_rss(self.URL)
            assert len(items) == 1
            assert items[0][0] == "Has Title"


# ═══════════════════════════════════════════
# fetch_all_rss (#67)
# ═══════════════════════════════════════════


class TestFetchAllRss:
    def test_preserva_orden_con_retrasos(self, monkeypatch):
        import time

        def lenta(url, source_name=""):
            if "b" in url:
                time.sleep(0.3)
            return [(f"titular de {url}", url)]

        monkeypatch.setattr(mod, "fetch_rss", lenta)
        sources = [("B", "https://b.example/rss"), ("A", "https://a.example/rss")]
        result = fetch_all_rss(sources, stagger=0)
        assert [items[0][1] for items in result] == [
            "https://b.example/rss",
            "https://a.example/rss",
        ]

    def test_corre_en_paralelo(self, monkeypatch):
        barrera = threading.Barrier(4, timeout=10)

        def con_barrera(url, source_name=""):
            barrera.wait()
            return []

        monkeypatch.setattr(mod, "fetch_rss", con_barrera)
        sources = [(f"S{i}", f"https://s{i}.example/rss") for i in range(4)]
        assert fetch_all_rss(sources, stagger=0) == [[], [], [], []]

    def test_fallo_aislado_no_rompe_lote(self, monkeypatch):
        def mixta(url, source_name=""):
            if "mala" in url:
                raise RuntimeError("caida")
            return [("ok", url)]

        monkeypatch.setattr(mod, "fetch_rss", mixta)
        sources = [("Buena", "https://ok.example/rss"), ("Mala", "https://mala.example/rss")]
        result = fetch_all_rss(sources, stagger=0)
        assert result[0] == [("ok", "https://ok.example/rss")]
        assert result[1] == []


# ═══════════════════════════════════════════
# Noticiero global (#149): 2-3 items por fuente, tope, dedupe
# ═══════════════════════════════════════════


class TestNoticieroGlobal:
    def test_constante_items_por_fuente(self):
        assert mod.ITEMS_POR_FUENTE == 3

    def test_tope_igual_telegram_max(self):
        from hermes_common import news_utils

        assert mod.MAX_CHARS_POR_SUBSECCION == news_utils.TELEGRAM_MAX_CHARS

    def test_tres_items_por_fuente_top_por_fecha(self):
        sources = [("Reuters", "https://reuters.example/rss")]
        fetched = [
            [
                ("T1", "https://example.com/1"),
                ("T2", "https://example.com/2"),
                ("T3", "https://example.com/3"),
                ("T4", "https://example.com/4"),
            ]
        ]
        block = mod.build_subsection_block("Subs", sources, fetched, set())
        assert "T1" in block and "T2" in block and "T3" in block
        assert "T4" not in block

    def test_tope_por_subseccion(self):
        sources = [("Reuters", "https://reuters.example/rss")]
        items = [(f"Título largo {i} " + "x" * 200, f"https://example.com/{i}") for i in range(10)]
        fetched = [items]
        with patch.object(mod, "MAX_CHARS_POR_SUBSECCION", 300):
            block = mod.build_subsection_block("Subs", sources, fetched, set())
        assert len(block) <= 300
        assert block.endswith("...")

    def test_dedupe_cross_seccion(self):
        seen: set = set()
        sources_a = [("Reuters", "https://reuters.example/rss")]
        fetched_a = [
            [("Compartida", "https://example.com/dup"), ("Propia A", "https://example.com/a")]
        ]
        block_a = mod.build_subsection_block("Sub A", sources_a, fetched_a, seen)
        assert "Compartida" in block_a

        sources_b = [("AP", "https://ap.example/rss")]
        fetched_b = [
            [("Compartida", "https://example.com/dup"), ("Propia B", "https://example.com/b")]
        ]
        block_b = mod.build_subsection_block("Sub B", sources_b, fetched_b, seen)
        assert "Compartida" not in block_b
        assert "Propia B" in block_b

    def test_subseccion_sin_contenido_retorna_vacio(self):
        block = mod.build_subsection_block("Subs", [("X", "https://x.example/rss")], [[]], set())
        assert block == ""


# ═══════════════════════════════════════════
# load_feeds: el config vive en la raíz del repo (#207)
# ═══════════════════════════════════════════


class TestLoadFeeds:
    """Regresión #207: tras mover los scripts a src/scripts/ (18ef447) la ruta
    se resolvía contra el módulo (src/scripts/config/feeds.json) en vez de
    contra la raíz del repo, y el cron de las 08:30 fallaba a diario."""

    def test_lee_config_desde_la_raiz_del_repo(self):
        feeds = mod.load_feeds()
        nombres = [nombre for nombre, _ in feeds]
        assert "💻 TECNOLOGÍA" in nombres, nombres
        assert len(feeds) >= 5

    def test_estructura_y_urls(self):
        feeds = mod.load_feeds()
        subseccion, fuentes = feeds[0][1][0]
        assert subseccion
        assert fuentes[0][0]  # nombre de la fuente
        assert fuentes[0][1].startswith("http")  # url


# ═══════════════════════════════════════════
# Presupuesto global de entrega (#212)
# ═══════════════════════════════════════════

FEEDS_DE_PRUEBA = [
    ("SECCIÓN A", [("sub", [("S", "https://s.example/rss")])]),
    ("SECCIÓN B", [("sub", [("S", "https://s.example/rss")])]),
    ("SECCIÓN C", [("sub", [("S", "https://s.example/rss")])]),
]


class TestPresupuestoDeEntrega:
    """Con 8 chunks (30 KB) el envío real falla con `Timed out` (#212, medido).

    El reporte debe caber en 2 chunks: el presupuesto es global, no por subsección.
    """

    @staticmethod
    def _fetch_unico(titulo="T" * 200):
        """URL distinta por llamada: el dedupe cross-sección si no, vacía las siguientes."""
        contador = iter(f"https://example.com/{n}" for n in range(1, 500))
        return lambda sources: [[(titulo, next(contador))]]

    def test_emite_solo_lo_que_cabe(self):
        emitidos: list = []
        omitidas = mod.emitir_secciones(
            FEEDS_DE_PRUEBA, self._fetch_unico(), emitidos.append, presupuesto=600
        )
        assert omitidas == ["SECCIÓN C"]
        assert sum(len(e) for e in emitidos) <= 600

    def test_no_pide_fuentes_cuando_el_presupuesto_esta_agotado(self):
        llamadas: list = []

        def fetch(sources):
            llamadas.append(sources)
            return [[("T" * 200, f"https://example.com/{len(llamadas)}")]]

        mod.emitir_secciones(FEEDS_DE_PRUEBA, fetch, lambda _t: None, presupuesto=600)
        assert len(llamadas) == 2  # la tercera sección se omite sin gastar red

    def test_reparte_el_presupuesto_entre_secciones(self):
        """Ninguna sección se come el presupuesto de las demás (#212)."""
        emitidos: list = []
        omitidas = mod.emitir_secciones(
            FEEDS_DE_PRUEBA, self._fetch_unico("T" * 2000), emitidos.append, presupuesto=900
        )
        assert omitidas == []
        assert sum(len(e) for e in emitidos) <= 900

    def test_nota_de_recorte(self):
        nota = mod.nota_de_recorte(["SECCIÓN C", "SECCIÓN D"])
        assert "SECCIÓN C" in nota and "SECCIÓN D" in nota
        assert "mañana" in nota

    def test_el_presupuesto_cabe_en_dos_chunks_de_telegram(self):
        # 2 chunks = 8192 unidades UTF-16 (4096 por mensaje); lo que no son
        # secciones (encabezado, pie, mercados, nota) va en la reserva.
        assert mod.MAX_CHARS_REPORTE + mod.RESERVA_FUERA_DE_SECCIONES <= 8192
