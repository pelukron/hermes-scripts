"""Tests para titans_daily.py (canal propio de Tennessee Titans, #356)."""

import json
import re
from pathlib import Path

from hermes_common import news_utils, telegram_chunks
from scripts.team_pipeline import build_report
from scripts.titans_daily import CONFIG, fetch_titans_official_impl

NewsItem = news_utils.NewsItem


def is_oficial(url: str) -> bool:
    return news_utils.is_oficial(url, CONFIG.sitios_oficiales)


def smells_like_rumor(title: str) -> bool:
    return news_utils.smells_like_rumor(title, CONFIG.rumor_keywords)


ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class TestConfigTitans:
    def test_edicion_us(self):
        assert CONFIG.edition == {"hl": "en-US", "gl": "US", "ceid": "US:en"}

    def test_sitio_oficial_declarado(self):
        assert CONFIG.sitios_oficiales == ["tennesseetitans.com"]

    def test_historial_propio(self):
        assert CONFIG.history_name == "titans-history.json"

    def test_encabezado_y_fuentes(self):
        assert "Tennessee Titans" in CONFIG.header_title
        assert "tennesseetitans.com" in CONFIG.sources_line

    def test_medios_usa(self):
        assert "espn.com" in CONFIG.sitios_confiables
        assert "thetennessean.com" in CONFIG.sitios_confiables

    def test_rumor_en_ingles(self):
        assert smells_like_rumor("Trade rumor: Titans to sign veteran QB") is True
        assert smells_like_rumor("Titans place star on injured reserve") is True

    def test_objetivo_en_ingles_sin_rumor(self):
        assert smells_like_rumor("Titans win 24-17 over Colts") is False

    def test_filtro_de_apuestas_declarado(self):
        """#386: los momios de los feeds directos no llenan la jornada."""
        assert "odds" in CONFIG.exclude_keywords
        assert "betting" in CONFIG.exclude_keywords
        assert "pick" not in CONFIG.exclude_keywords, "en singular da falsos positivos (Draft Pick)"

    def test_dominio_oficial_cuenta_como_confirmado(self):
        assert is_oficial("https://www.tennesseetitans.com/news/titans-sign-db") is True
        assert is_oficial("https://www.espn.com/nfl/story/_/id/1/titans") is False

    def test_seccion_jornada_declarada(self):
        """#386: la jornada sale de feeds directos (FOX, CBS) más NFL.com."""
        extra = CONFIG.extra_section
        assert extra is not None
        assert "{count}" in extra.titulo
        assert extra.categoria == "liga"
        assert [nombre for nombre, _ in extra.feeds] == ["FOX Sports", "CBS Sports"]
        assert all(url.startswith("https://") for _, url in extra.feeds)
        assert extra.query == "site:nfl.com"


class TestFetchTitansOfficial:
    def test_vacio_declarado(self):
        """Sin fetcher real (#356): el sitio es React y el listado no viene en el HTML."""
        assert fetch_titans_official_impl(lambda *_a, **_k: None) == []
        assert "React" in fetch_titans_official_impl.__doc__


def test_queries_usan_frases_entre_comillas():
    """La query abre con frase citada; AND o paréntesis dejan el feed en 0 entries."""
    patron = r'^"[^"]+"(?:\s+OR\s+"[^"]+"|\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+)*$'
    for key, q in CONFIG.queries.items():
        assert re.fullmatch(patron, q), f"QUERIES[{key}] no cumple sintaxis: {q}"
        assert "(" not in q and ")" not in q, f"QUERIES[{key}] usa paréntesis: {q}"
        assert " AND " not in q, f"QUERIES[{key}] usa AND explícito: {q}"


def _mk_confirmada(i: int) -> NewsItem:
    return NewsItem(
        title=f"Titans note {i}",
        link=f"https://ejemplo.com/{i}",
        source="ESPN",
        confiable=True,
        origin="gn",
        category="confirmadas",
    )


def _mk_liga(i: int) -> NewsItem:
    return NewsItem(
        title=f"NFL league note {i}",
        link=f"https://ejemplo.com/liga/{i}",
        source="ESPN",
        confiable=True,
        origin="gn",
        category="liga",
    )


def _mk_rumor(i: int) -> NewsItem:
    return NewsItem(
        title=f"Receptor estrella pide salir segun rumores {i}",
        link=f"https://ejemplo.com/rumor/{i}",
        source="Blog",
        origin="gn",
        category="rumores",
    )


def test_reporte_tres_bloques_con_techo(tmp_path):
    """#386: header + jornada + la sección única del equipo; el mensaje cabe en 1 trozo."""
    confirmadas = [_mk_confirmada(i) for i in range(12)]
    liga = [_mk_liga(i) for i in range(3)]
    rumores = [_mk_rumor(0)]
    por_categoria = {"confirmadas": confirmadas, "rumores": rumores, "liga": liga}
    titulares = {
        "FOX Sports": "Achane se pierde la temporada con el cruzado roto",
        "CBS Sports": "Mayfield sale con el pulgar dislocado",
    }

    def fetch_google(_query: str, category: str) -> list:
        return list(por_categoria.get(category, []))

    def fetch_rss(_url: str, source: str, category: str) -> list:
        return [
            NewsItem(
                title=titulares[source],
                link=f"https://{source.split()[0].lower()}.com/nfl/1",
                source=source,
                confiable=True,
                origin=f"rss:{source}",
                category=category,
            )
        ]

    blocks = build_report(
        CONFIG,
        history_path=str(tmp_path / CONFIG.history_name),
        fetch_google_news=fetch_google,
        fetch_rss=fetch_rss,
        fetch_official=lambda: [],
        enrich_official=lambda items: items,
    )

    assert len(blocks) == 3
    assert "Tennessee Titans" in blocks[0]
    bloque_jornada = [b for b in blocks if "La jornada" in b][0]
    assert blocks.index(bloque_jornada) == 1
    assert "Achane se pierde la temporada" in bloque_jornada
    assert "Mayfield sale con el pulgar" in bloque_jornada
    equipo = [b for b in blocks if "TENNESSEE TITANS" in b][0]
    assert "CONFIRMADO" not in equipo and "RUMORES" not in equipo
    bullets = [line for line in equipo.splitlines() if line.startswith("- ")]
    # Techo por presupuesto (#386): con los enlaces cortos de la prueba caben
    # las 13, así que el contador ya no se queda en 8 y no hay " de ".
    assert len(bullets) == 13
    # 12 confirmadas + 1 rumor: el rumor va al final de la sección única y le
    # queda su hueco, así que la etiqueta 📰 sí se ve.
    assert bullets[-1].startswith("- 📰 ")
    assert "Receptor estrella" in bullets[-1]
    header = equipo.splitlines()[0]
    assert header == "**🏈 TENNESSEE TITANS** (13)"
    mensaje = "\n---\n".join(blocks)
    assert telegram_chunks(mensaje) <= 1, f"mensaje pasa de 1 trozo: {len(mensaje)}"
    assert len(ISO_DATE.findall(mensaje)) <= 1, "el mensaje repite fecha"


def test_entrada_del_manifiesto():
    """El job existe en el manifiesto con su entry point, wrapper y destino (#356)."""
    root = Path(__file__).resolve().parents[1]
    with open(root / "cron" / "jobs.json", encoding="utf-8") as f:
        manifiesto = json.load(f)
    jobs = {j["name"]: j for j in manifiesto["jobs"]}
    job = jobs["titans-daily"]
    assert job["schedule"] == "0 9 * * *"
    assert job["command"] == "uv run titans-daily"
    assert job["wrapper"] == "titans-daily.sh"
    assert job["deliver"] == "${titans}"
