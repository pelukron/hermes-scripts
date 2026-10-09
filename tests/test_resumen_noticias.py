"""Tests para funciones clave de resumen-noticias-diario.py"""

import importlib.util  # noqa: E402
import os
import threading
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlparse

# Add script dir to path para importar
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        parsed = urlparse(result)
        assert parsed.scheme == "https"
        assert parsed.hostname == "news.google.com"


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

    def test_topes_salen_de_delivery(self):
        """Fuente única (#423): los números no cambian, el dueño sí."""
        from hermes_common import delivery

        assert mod.MAX_CHARS_REPORTE == delivery.REPORT_BUDGET == 7100
        assert mod.MAX_CHARS_LINEA == delivery.LINE_BUDGET == 3800
        assert mod.MAX_CHARS_POR_SUBSECCION == 3000

    def test_suplementario_mide_en_utf16(self):
        """🛒 = 1 code point y 2 unidades UTF-16: cabe para len() y no para el seam."""
        from hermes_common import delivery

        sources = [("Reuters", "https://reuters.example/rss")]
        fetched = [[("Oferta 🛒 hoy", "https://example.com/1")]]
        linea = "  [Oferta 🛒 hoy](https://example.com/1)"
        assert delivery.utf16_len(linea) == len(linea) + 1
        cuota = len("*Subs*") + 1 + len("• *Reuters*") + 1 + len(linea) + 1
        assert mod.build_subsection_block("Subs", sources, fetched, set(), cuota=cuota) == ""
        control = mod.build_subsection_block("Subs", sources, fetched, set(), cuota=cuota + 1)
        assert "Oferta 🛒 hoy" in control

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
        # Los titulares se recortan a MAX_CHARS_TITULO (#212), así que para
        # exceder el tope de subsección hacen falta más de ITEMS_POR_FUENTE.
        with (
            patch.object(mod, "MAX_CHARS_POR_SUBSECCION", 300),
            patch.object(mod, "ITEMS_POR_FUENTE", 10),
        ):
            block = mod.build_subsection_block("Subs", sources, fetched, set())
        assert len(block) <= 300
        # #278: el bloque termina en un item completo, no en '...' (el recorte es por item,
        # no por carácter: antes cortaba a mitad de la URL y dejaba el enlace sin cerrar).
        assert block.rstrip().splitlines()[-1].endswith(")")

    def test_dos_fuentes_entran_antes_del_segundo_item_de_la_primera(self):
        """El reparto es por rondas: la segunda fuente no espera a que la primera se llene."""
        sources = [("Reuters", "https://reuters.example/rss"), ("AP", "https://ap.example/rss")]
        largo = "Titular largo " + "x" * 60
        fetched = [
            [(largo, "https://example.com/r1"), (largo + " 2", "https://example.com/r2")],
            [(largo, "https://example.com/a1")],
        ]
        # Cuota para el encabezado, los dos bullets y un item por fuente: no para dos de Reuters.
        with patch.object(mod, "MAX_CHARS_POR_SUBSECCION", 260):
            block = mod.build_subsection_block("Subs", sources, fetched, set())
        assert "• *Reuters*" in block and "• *AP*" in block
        assert block.count("\n  [") == 2  # un item por fuente, no los dos de la primera

    def test_una_fuente_cuya_primera_no_cabe_entra_por_la_siguiente(self):
        """Un primer item enorme no condena a su fuente: la ronda siguiente prueba el siguiente."""
        sources = [("Reuters", "https://reuters.example/rss")]
        enorme = "Titular enorme " + "x" * 200
        fetched = [
            [(enorme, "https://example.com/" + "u" * 200), ("Corto", "https://example.com/c1")]
        ]
        with patch.object(mod, "MAX_CHARS_POR_SUBSECCION", 220):
            block = mod.build_subsection_block("Subs", sources, fetched, set())
        assert "Corto" in block
        assert "• *Reuters*" in block

    def test_el_item_que_no_cabe_queda_contado_por_fuente(self):
        """#355: la ronda siguiente salva la fuente, y el ítem que no cupo se declara."""
        sources = [("Reuters", "https://reuters.example/rss"), ("AP", "https://ap.example/rss")]
        enorme = "Titular enorme " + "x" * 200
        fetched = [
            [(enorme, "https://example.com/" + "u" * 200), ("Corto", "https://example.com/c1")],
            [("También largo " + "y" * 200, "https://example.com/" + "a" * 200)],
        ]
        descartes: list = []
        with patch.object(mod, "MAX_CHARS_POR_SUBSECCION", 220):
            block = mod.build_subsection_block(
                "Wires", sources, fetched, set(), descartes=descartes
            )
        assert "Corto" in block
        assert descartes == [("Wires", "Reuters"), ("Wires", "AP")]
        nota = mod.nota_de_cuota(descartes)
        assert nota == "*fuera de cuota: Wires — Reuters 1, AP 1*\n"
        assert "_" not in nota
        assert nota.strip().count("\n") == 0
        assert len(nota.strip()) <= mod.MAX_CHARS_LINEA

    def test_sin_descartes_la_nota_de_cuota_calla(self):
        assert mod.nota_de_cuota([]) == ""

    def test_la_nota_de_cuota_no_pasa_el_tope_de_linea(self):
        pares = [(f"Sección {i} con nombre largo", f"Fuente {i}") for i in range(400)]
        nota = mod.nota_de_cuota(pares)
        assert len(nota.strip()) <= mod.MAX_CHARS_LINEA
        assert nota.strip().count("\n") == 0
        assert "+" in nota and "más" in nota
        assert nota.startswith("*fuera de cuota:")
        assert nota.strip().endswith("*")

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


class TestPresupuestoDeEntrega:
    """Con 8 chunks (30 KB) el envío real falla con `Timed out` (#212, medido).

    El reporte debe caber en 2 chunks: el presupuesto es global, no por subsección.
    """

    @staticmethod
    def _feeds(n_secciones):
        return [
            (f"SECCIÓN {i}", [("sub", [("S", f"https://s.example/rss{i}")])])
            for i in range(n_secciones)
        ]

    @staticmethod
    def _fetch(n_items=3):
        """Items de ~100 chars con URL única; el dedupe cross-sección vacía las siguientes si no."""
        contador = iter(range(1, 99999))
        return lambda sources: [
            [
                (f"Titular {n} " + "T" * 60, f"https://example.com/{n}-{next(contador)}")
                for n in range(n_items)
            ]
        ]

    def test_emite_solo_lo_que_cabe(self):
        emitidos: list = []
        omitidas = mod.emitir_secciones(
            self._feeds(3), self._fetch(), emitidos.append, presupuesto=600
        )
        assert omitidas == ["SECCIÓN 2"]
        assert sum(len(e) for e in emitidos) <= 600

    def test_no_pide_fuentes_cuando_el_presupuesto_esta_agotado(self):
        llamadas: list = []
        fetch = self._fetch()

        def fetch_contado(sources):
            llamadas.append(sources)
            return fetch(sources)

        mod.emitir_secciones(self._feeds(3), fetch_contado, lambda _t: None, presupuesto=600)
        assert len(llamadas) == 2  # la tercera sección se omite sin gastar red

    def test_reparte_el_presupuesto_entre_secciones(self):
        """Ninguna sección se come el presupuesto de las demás (#212)."""
        emitidos: list = []
        omitidas = mod.emitir_secciones(
            self._feeds(3), self._fetch(), emitidos.append, presupuesto=900
        )
        assert omitidas == []
        assert sum(len(e) for e in emitidos) <= 900

    def test_nota_de_recorte(self):
        nota = mod.nota_de_recorte(["SECCIÓN C", "SECCIÓN D"])
        assert "SECCIÓN C" in nota and "SECCIÓN D" in nota
        assert "mañana" in nota
        assert "*Por presupuesto" in nota
        assert "_Por presupuesto" not in nota

    def test_el_reporte_cabe_en_dos_mensajes(self):
        # Medido (#278): el chunker de Hermes (gateway/platforms/base.py `truncate_message`)
        # corta en el último '\n' del bloque, así que el techo es por MENSAJE y no por corrida.
        # #212 había fijado 1 mensaje (3200) y ese techo forzó el corte que rompió el diseño.
        # 2 mensajes de 4096 menos el marco del cron (~200) y el indicador de chunk (10).
        assert mod.MAX_CHARS_REPORTE + mod.RESERVA_FUERA_DE_SECCIONES <= 2 * 4096 - 300


class TestTituloDeItem:
    """Títulos largos: al leer el reporte se paga el título completo (#212).

    Con el fallback a texto plano, la URL de Google News (~200 chars) se ve
    entera al lado del título: un titular de 100+ chars por noticia hace
    ilegible el mensaje.
    """

    TITULAR_LARGO = (
        "Aramco halts October crude deliveries to some European refiners "
        "after pipeline attack, Bloomberg reports"
    )

    def test_titular_largo_se_recorta(self):
        bloque = mod.build_subsection_block(
            "Sub",
            [("Reuters", "https://r.example/rss")],
            [[(self.TITULAR_LARGO, "https://example.com/a")]],
            set(),
        )
        assert self.TITULAR_LARGO not in bloque
        assert "Aramco halts October" in bloque
        assert "..." in bloque

    def test_titular_corto_no_se_toca(self):
        bloque = mod.build_subsection_block(
            "Sub",
            [("Reuters", "https://r.example/rss")],
            [[("Corto y claro", "https://example.com/b")]],
            set(),
        )
        assert "Corto y claro" in bloque
        assert "..." not in bloque

    def test_tope_de_titulo_es_razonable(self):
        assert 60 <= mod.MAX_CHARS_TITULO <= 100

    def test_quita_parentesis_que_tiran_markdownv2(self):
        """Los paréntesis del feed hacen que el envío caiga a texto plano (#212)."""
        bloque = mod.build_subsection_block(
            "Sub",
            [("SCMP (HK/CN)", "https://r.example/rss")],
            [[("Titular (Bloomberg reports)", "https://example.com/c")]],
            set(),
        )
        assert "(HK/CN)" not in bloque
        assert "(Bloomberg reports)" not in bloque
        assert "SCMP HK/CN" in bloque
        assert "Bloomberg reports" in bloque

    def test_sin_parentesis_no_toca_lo_demas(self):
        assert mod.sin_parentesis("Inflación (+2.1%) en México") == "Inflación +2.1% en México"


# ═══════════════════════════════════════════
# Diseño del diario (#278): el recorte es por item, no por carácter
# ═══════════════════════════════════════════

URL_GOOGLE_NEWS = "https://news.google.com/rss/articles/CBMi" + "A" * 220


def _enlaces_abiertos(texto):
    from hermes_common import markdown_v2_link_issues

    return markdown_v2_link_issues(texto)


def _lineas_colgadas(texto):
    return [linea for linea in texto.splitlines() if linea.rstrip().endswith("...")]


class TestRecortePorItem:
    """Con la URL de Google News (241 chars), cortar por carácter partía el enlace."""

    @staticmethod
    def _bloque(cuota, fuentes=("Reuters", "AP")):
        sources = [(nombre, "http://rss") for nombre in fuentes]
        fetched = [
            [(f"Titular {i} de {nombre}", f"{URL_GOOGLE_NEWS}{nombre}{i}") for i in range(2)]
            for nombre in fuentes
        ]
        return mod.build_subsection_block("Wires", sources, fetched, set(), cuota=cuota)

    def test_la_cuota_no_parte_enlaces(self):
        bloque = self._bloque(400)
        assert _enlaces_abiertos(bloque) == []
        assert _lineas_colgadas(bloque) == []

    def test_no_emite_bullet_de_fuente_sin_items(self):
        bloque = self._bloque(400)
        assert bloque.strip().splitlines()[-1].startswith("  ["), bloque

    def test_cuota_minima_no_emite_nada_en_vez_de_medio_item(self):
        assert self._bloque(120) == ""

    def test_un_item_que_no_cupo_no_se_marca_como_visto(self):
        vistos: set = set()
        sources = [("Reuters", "http://rss")]
        fetched = [
            [(f"Titular {i}", f"{URL_GOOGLE_NEWS}{i}") for i in range(2)],
        ]
        mod.build_subsection_block("Wires", sources, fetched, vistos, cuota=120)
        assert vistos == set()
        mod.build_subsection_block("Wires", sources, fetched, vistos, cuota=400)
        assert len(vistos) == 1


class TestRepartoDeSeccion:
    """El techo de la sección se reparte: sin reparto la primera subsección se come todo (#278)."""

    def _emitidos(self, presupuesto, subsections=2):
        subs = [
            (f"Sub {letra}", [(f"Fuente {letra}", f"http://rss/{letra}")])
            for letra in "ABCD"[:subsections]
        ]
        feeds = [("SECCIÓN", subs)]

        def fetch(sources):
            return [
                [(f"Titular {i} de {nombre}", f"{URL_GOOGLE_NEWS}{nombre}{i}") for i in range(3)]
                for nombre, _ in sources
            ]

        emitidos: list[str] = []
        with patch.object(mod.time, "sleep", lambda *_a, **_k: None):
            omitidas = mod.emitir_secciones(feeds, fetch, emitidos.append, presupuesto=presupuesto)
        return "\n".join(emitidos), omitidas

    def test_ninguna_subseccion_sale_sin_item_completo(self):
        texto, _ = self._emitidos(900)
        lineas = texto.splitlines()
        for i, linea in enumerate(lineas):
            if linea.startswith("*Sub "):
                assert lineas[i + 1].startswith("• *"), lineas[i : i + 3]
                assert lineas[i + 2].startswith("  [") and lineas[i + 2].endswith(")"), lineas[
                    i : i + 3
                ]

    def test_no_parte_enlaces_con_presupuesto_justo(self):
        texto, _ = self._emitidos(900)
        assert _enlaces_abiertos(texto) == []
        assert _lineas_colgadas(texto) == []

    def test_con_presupuesto_amplio_salen_mas_tomas(self):
        corto, _ = self._emitidos(900)
        largo, _ = self._emitidos(2400)
        assert len(largo) > len(corto)


class TestDialectoMarkdown:
    """Hermes escapa `_` en texto plano: las itálicas salen con guiones bajos a la vista.

    Mismo caso en las subsecciones y en el sello de versión (#278).
    """

    def test_subseccion_usa_asteriscos(self):
        bloque = mod.build_subsection_block(
            "Wires", [("Reuters", "http://rss")], [[("Titular", "https://e.com/a")]], set()
        )
        assert "*Wires*" in bloque
        assert "_Wires_" not in bloque

    def test_footer_de_fuentes_sin_underscore_huerfano(self):
        fuente = Path(__file__).resolve().parent.parent / "src" / "scripts"
        texto = (fuente / "resumen_noticias_diario.py").read_text(encoding="utf-8")
        assert 'footer_line += "_\\n"' not in texto


class TestPolymarketSection:
    """El bloque de Polymarket llega por el logger del padre (#422)."""

    def test_el_texto_vuelve_por_el_logger_del_padre(self):
        with (
            patch.object(
                mod.polymarket_diario,
                "fetch_classified_markets",
                return_value=({}, 0),
            ),
            patch.object(mod.polymarket_diario, "build_block", return_value="linea 1\nlinea 2"),
            patch.object(mod, "log") as mock_log,
        ):
            mod.emit_polymarket_block()
        emitidos = [c.args[0] for c in mock_log.info.call_args_list]
        assert emitidos == ["linea 1", "linea 2"]

    def test_linea_larga_se_ajusta_con_prepare(self):
        larga = "L" * (mod.delivery.LINE_BUDGET + 100)
        with (
            patch.object(
                mod.polymarket_diario,
                "fetch_classified_markets",
                return_value=({}, 0),
            ),
            patch.object(
                mod.polymarket_diario,
                "build_block",
                return_value=f"encabezado\n{larga}",
            ),
            patch.object(mod, "log") as mock_log,
        ):
            mod.emit_polymarket_block()
        emitidos = [c.args[0] for c in mock_log.info.call_args_list]
        assert larga not in emitidos
        assert "encabezado" in emitidos
        assert any("+1 fuera" in linea for linea in emitidos)

    def test_si_falla_avisa_y_el_diario_sigue(self):
        with (
            patch.object(
                mod.polymarket_diario,
                "fetch_classified_markets",
                side_effect=RuntimeError("boom"),
            ),
            patch.object(mod, "log") as mock_log,
        ):
            mod.emit_polymarket_block()
        mock_log.warning.assert_called_once()
        mock_log.info.assert_not_called()

    def test_sin_subprocess_para_este_caso(self):
        fuente = Path(__file__).resolve().parent.parent / "src" / "scripts"
        texto = (fuente / "resumen_noticias_diario.py").read_text(encoding="utf-8")
        assert "subprocess" not in texto
