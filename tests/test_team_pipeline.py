"""Seam de TeamPipeline: un ensamble, dos configs, y un guard contra la deriva."""

from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_common import news_utils, telegram_chunks
from scripts.team_pipeline import ExtraSection, TeamConfig, build_report, expose

NewsItem = news_utils.NewsItem

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src" / "scripts"


def _config(**overrides) -> TeamConfig:
    base = dict(
        history_name="equipo-history.json",
        queries={"confirmadas": '"Equipo"', "rumores": '"Equipo" fichaje'},
        sitios_oficiales=["equipo.test"],
        header_title="**Equipo — Noticias del día**",
        sources_line="Fuentes: prueba",
        prefilter_official=False,
        announce_overflow=False,
        edition={"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"},
    )
    base.update(overrides)
    return TeamConfig(**base)


def _notas(n: int) -> list[NewsItem]:
    return [
        NewsItem(
            title=f"Asunto-{i:04d}-abc relleno que no colapsa",
            link=f"https://ejemplo.com/nota-{i}",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        )
        for i in range(n)
    ]


def _report(config: TeamConfig, items: list[NewsItem], tmp_path: Path) -> list[str]:
    def fetch_google(query: str, category: str) -> list[NewsItem]:
        return items if category == "confirmadas" else []

    return build_report(
        config,
        history_path=str(tmp_path / config.history_name),
        fetch_google_news=fetch_google,
        fetch_official=list,
        enrich_official=lambda found: found,
    )


def _confirmado(blocks: list[str]) -> str:
    return next(block for block in blocks if "CONFIRMADO" in block)


def test_el_contador_de_tigres_anuncia_el_recorte(tmp_path):
    blocks = _report(
        _config(announce_overflow=True, history_name="tigres.json"), _notas(12), tmp_path
    )
    header = _confirmado(blocks).splitlines()[0]
    assert header.startswith("**✅ CONFIRMADO** (8 de 12)")


def test_el_contador_de_rayados_cuenta_el_total(tmp_path):
    blocks = _report(
        _config(announce_overflow=False, history_name="rayados.json"), _notas(12), tmp_path
    )
    header = _confirmado(blocks).splitlines()[0]
    assert header.startswith("**✅ CONFIRMADO** (12)")
    assert " de " not in header
    bullets = [line for line in _confirmado(blocks).splitlines() if line.startswith("- ")]
    assert len(bullets) == 8


def test_las_italicas_del_ensamble_usan_asteriscos(tmp_path):
    blocks = _report(_config(history_name="vacio.json"), [], tmp_path)
    texto = "\n".join(blocks)
    assert "*Actualizado:" in blocks[0]
    assert "_Actualizado" not in texto
    assert "*No se encontraron noticias confirmadas" in _confirmado(blocks)
    assert "_No se encontraron" not in texto


def test_el_recorte_no_parte_una_url():
    from scripts.team_pipeline import fit_block

    url = "https://news.google.com/rss/articles/" + ("a" * 80)
    line = f"- 📰 **Medio**: [{url}]({url})"
    fitted = fit_block("\n".join([line, line]), limit=len(line) + 5)
    assert fitted == line
    assert url in fitted


def test_las_listas_compartidas_viven_una_sola_vez():
    pipeline = (SCRIPTS / "team_pipeline.py").read_text(encoding="utf-8")
    assert pipeline.count('"milenio.com"') == 1
    assert pipeline.count('"podría"') == 1
    for name in ("resumen_rayados_diario.py", "resumen_tigres_diario.py"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "HistoryManager" not in text
        assert "BeautifulSoup" not in text
        assert "milenio.com" not in text
        assert "expose(" in text
        assert "podría" not in text
        assert len(text.splitlines()) < 90


def _exposed(config: TeamConfig) -> dict:
    """Devuelve el namespace que `expose` cuelga en un módulo de equipo."""
    ns: dict = {}
    expose(
        ns,
        config,
        request=lambda *a, **k: None,
        official_impl=lambda _request: [],
        detail_label="equipo.test",
        official_name="fetch_official_listing",
        detail_name="fetch_official_detail",
        enrich_name="enrich_official_items",
    )
    return ns


def _edicion_que_llega_al_feed(config: TeamConfig) -> object:
    """Captura el argumento `edition` con el que el config pide el feed."""
    capturado: dict = {}

    def falso(query, category, *args):
        capturado["edition"] = args[3]
        return []

    with patch("hermes_common.news_utils.fetch_google_news", side_effect=falso):
        _exposed(config)["fetch_google_news"]("'Equipo'", "confirmadas")
    return capturado["edition"]


def test_el_config_del_equipo_pasa_su_edicion_al_feed():
    """La edición viaja del config al constructor de la URL (ADR 0010, issue #357)."""
    en_eeuu = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    assert _edicion_que_llega_al_feed(_config(edition=en_eeuu)) == en_eeuu


def test_el_config_exige_la_edicion():
    """Sin edición el config no se construye: no hay herencia por omisión (ADR 0010)."""
    sin_edicion = {
        "history_name": "sin-edicion.json",
        "queries": {},
        "sitios_oficiales": [],
        "header_title": "",
        "sources_line": "",
        "prefilter_official": False,
        "announce_overflow": False,
    }
    with pytest.raises(TypeError):
        TeamConfig(**sin_edicion)  # type: ignore[call-arg]


def test_los_reportes_vivos_declaran_la_edicion_mexicana():
    """La edición de Rayados y Tigres vive en su config, no en la librería (ADR 0010)."""
    from scripts.resumen_rayados_diario import CONFIG as RAYADOS
    from scripts.resumen_tigres_diario import CONFIG as TIGRES

    for config in (RAYADOS, TIGRES):
        assert config.edition == {"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"}
        url = news_utils.build_google_news_url("Equipo", config.edition)
        assert url.endswith("&hl=es-419&gl=MX&ceid=MX:es-419")


# ═══════════════════════════════════════════
# Sección de liga (#359): opcional y con bloque propio
# ═══════════════════════════════════════════


def _config_liga(**overrides) -> TeamConfig:
    return _config(
        extra_section=ExtraSection(
            titulo="**🏈 LIGA** ({count})",
            query='"Liga"',
            categoria="confirmadas",
        ),
        **overrides,
    )


def _notas_liga(n: int) -> list[NewsItem]:
    return [
        NewsItem(
            title=f"Jornada-{i:04d} resultado que no colapsa",
            link=f"https://ejemplo.com/liga-{i}",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        )
        for i in range(n)
    ]


def _report_liga(
    config: TeamConfig,
    equipo: list[NewsItem],
    liga: list[NewsItem],
    tmp_path: Path,
) -> list[str]:
    def fetch_google(query: str, category: str) -> list[NewsItem]:
        if config.extra_section is not None and query == config.extra_section.query:
            return liga
        return equipo if category == "confirmadas" else []

    return build_report(
        config,
        history_path=str(tmp_path / config.history_name),
        fetch_google_news=fetch_google,
        fetch_official=list,
        enrich_official=lambda found: found,
    )


def test_sin_extra_el_render_sigue_de_tres_bloques(tmp_path):
    """Sin declararla, el render es el de siempre: header + CONFIRMADO + RUMORES."""
    assert _config().extra_section is None
    blocks = _report(_config(history_name="sin-liga.json"), _notas(2), tmp_path)
    assert len(blocks) == 3
    assert "LIGA" not in "\n".join(blocks)


def test_con_extra_el_reporte_trae_la_liga_tras_el_header(tmp_path):
    blocks = _report_liga(
        _config_liga(history_name="con-liga.json"), _notas(2), _notas_liga(2), tmp_path
    )
    assert len(blocks) == 4
    assert blocks[1].splitlines()[0].startswith("**🏈 LIGA** (2)")
    assert "CONFIRMADO" in blocks[2]
    assert "RUMORES" in blocks[3]


def test_dedupe_conjunto_entre_liga_y_equipo(tmp_path):
    """Mismo titular con distinto link en liga y equipo: sale una sola vez."""
    titulo = "Duelo de la jornada sin guiones"
    liga = [
        NewsItem(
            title=titulo,
            link="https://ejemplo.com/liga-x",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        )
    ]
    equipo = [
        NewsItem(
            title=titulo,
            link="https://ejemplo.com/equipo-x",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        )
    ]
    blocks = _report_liga(_config_liga(history_name="dedupe.json"), equipo, liga, tmp_path)
    assert "\n---\n".join(blocks).count(titulo) == 1


def test_query_extra_con_frase_citada():
    """La query de liga abre con frase citada; AND o paréntesis dejan el feed en 0."""
    patron = r'^"[^"]+"(?:\s+OR\s+"[^"]+"|\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+)*$'
    import re

    q = _config_liga().extra_section.query
    assert re.fullmatch(patron, q), f"extra_section.query no cumple sintaxis: {q}"
    assert "(" not in q and ")" not in q
    assert " AND " not in q


def test_bloques_con_liga_caben_en_un_trozo_con_una_fecha(tmp_path):
    """12 + 12 con techo 8: 1 mensaje = 1 trozo y sin repetir fecha (ADR 0005)."""
    import re

    blocks = _report_liga(
        _config_liga(history_name="techo.json"), _notas(12), _notas_liga(12), tmp_path
    )
    mensaje = "\n---\n".join(blocks)
    assert telegram_chunks(mensaje) <= 1, f"mensaje pasa de 1 trozo: {len(mensaje)}"
    assert len(re.findall(r"\d{4}-\d{2}-\d{2}", mensaje)) <= 1


def test_los_vivos_no_declaran_extra_section():
    """La liga es opt-in: Rayados y Tigres salen igual que antes (#359)."""
    from scripts.resumen_rayados_diario import CONFIG as RAYADOS
    from scripts.resumen_tigres_diario import CONFIG as TIGRES

    assert RAYADOS.extra_section is None
    assert TIGRES.extra_section is None
