"""Seam de TeamPipeline: un ensamble, dos configs, y un guard contra la deriva."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_common import delivery, news_utils, telegram_chunks
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


def test_el_recorte_no_parte_una_url_y_se_declara():
    """El recorte lo hace el módulo: por línea entera, y la pérdida se declara."""
    from hermes_common import prepare

    url = "https://news.google.com/rss/articles/" + ("a" * 80)
    line = f"- 📰 **Medio**: [{url}]({url})"
    block = "\n".join([line, line, line])

    (result,) = prepare([block], message_budget=len(line) + 30)

    # Caben una línea y la nota: las otras dos se descartan enteras y se declaran.
    assert result.dropped == 2
    emitted = result.text.splitlines()
    assert emitted[0] == line, "la línea emitida conserva su URL completa"
    assert emitted[-1].endswith("fuera"), emitted[-1]


def test_las_listas_compartidas_viven_una_sola_vez():
    pipeline = (SCRIPTS / "team_pipeline.py").read_text(encoding="utf-8")
    assert pipeline.count('"milenio.com"') == 1
    assert pipeline.count('"podría"') == 1
    assert "def fetch_rayados_com" not in pipeline
    assert "def fetch_tigres_com" not in pipeline
    for name, fetcher in (
        ("resumen_rayados_diario.py", "def fetch_rayados_com"),
        ("resumen_tigres_diario.py", "def fetch_tigres_com"),
    ):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "HistoryManager" not in text
        assert "BeautifulSoup" in text
        assert fetcher in text
        assert "milenio.com" not in text
        assert "expose(" in text
        assert "podría" not in text
        assert len(text.splitlines()) < 150
    tigres = (SCRIPTS / "resumen_tigres_diario.py").read_text(encoding="utf-8")
    for helper in ("def listing_time_of", "def _tigres_title", "def _tigres_article"):
        assert helper in tigres


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


# dedupe por historia en el ensamble (#386): opt-in, Rayados y Tigres intactos


def _misma_historia(n: int) -> list[NewsItem]:
    """n medios contando el mismo partido, con titulares distintos entre sí."""
    titulares = [
        "What we learned from Tennessee Titans' 12-7 loss to New York Giants",
        "🎥 Highlights: New York Giants 12, Tennessee Titans 7",
        "What we learned from New York Giants' 12-7 win over Tennessee Titans",
    ]
    return [
        NewsItem(
            title=titulares[i % len(titulares)],
            link=f"https://ejemplo.com/partido-{i}",
            source=f"Medio-{i}",
            confiable=True,
            origin="gn",
            category="confirmadas",
        )
        for i in range(n)
    ]


def _renglones(bloque: str) -> list[str]:
    return [line for line in bloque.splitlines() if line.startswith("- ")]


def test_sin_la_bandera_la_repeticion_sigue_igual(tmp_path):
    """Rayados y Tigres no declaran `dedupe_story`: su salida no cambia (#386)."""
    assert _config().dedupe_story is False
    blocks = _report(_config(history_name="sin-historia.json"), _misma_historia(3), tmp_path)
    assert len(_renglones(_confirmado(blocks))) == 3


def test_con_la_bandera_la_misma_historia_sale_una_vez(tmp_path):
    blocks = _report(
        _config(history_name="con-historia.json", dedupe_story=True),
        _misma_historia(4),
        tmp_path,
    )
    renglones = _renglones(_confirmado(blocks))
    assert len(renglones) == 1
    assert "12-7" in renglones[0]


def test_la_bandera_no_junta_noticias_distintas(tmp_path):
    distintas = [
        NewsItem(
            title="Titans face offensive line injury concerns heading into Week 4",
            link="https://ejemplo.com/a",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        ),
        NewsItem(
            title="Titans open as 11-point underdogs vs. Ravens in Week 4",
            link="https://ejemplo.com/b",
            source="Medio",
            confiable=True,
            origin="gn",
            category="confirmadas",
        ),
    ]
    blocks = _report(_config(history_name="distintas.json", dedupe_story=True), distintas, tmp_path)
    assert len(_renglones(_confirmado(blocks))) == 2


def test_el_canal_de_los_titans_declara_la_bandera():
    from scripts.titans_daily import CONFIG as TITANS

    assert TITANS.dedupe_story is True
    from scripts.resumen_rayados_diario import CONFIG as RAYADOS
    from scripts.resumen_tigres_diario import CONFIG as TIGRES

    assert RAYADOS.dedupe_story is False
    assert TIGRES.dedupe_story is False


# sección única del equipo con etiqueta por línea (#386)


def _report_dos_listas(
    config: TeamConfig,
    confirmadas: list[NewsItem],
    rumores: list[NewsItem],
    tmp_path: Path,
) -> list[str]:
    def fetch_google(query: str, category: str) -> list[NewsItem]:
        return rumores if category == "rumores" else confirmadas

    return build_report(
        config,
        history_path=str(tmp_path / config.history_name),
        fetch_google_news=fetch_google,
        fetch_official=list,
        enrich_official=lambda found: found,
    )


def _item(titulo: str, *, oficial=False, confiable=False, categoria="confirmadas") -> NewsItem:
    return NewsItem(
        title=titulo,
        link=f"https://ejemplo.com/{titulo[:20].replace(' ', '-')}",
        source="Medio",
        oficial=oficial,
        confiable=confiable,
        origin="gn",
        category=categoria,
    )


def _seccion_equipo(blocks: list[str]) -> str:
    return next(b for b in blocks if "EL EQUIPO" in b or "TENNESSEE TITANS" in b)


def test_sin_la_bandera_siguen_los_dos_bloques(tmp_path):
    assert _config().single_section is False
    blocks = _report(_config(history_name="dos-bloques.json"), _notas(2), tmp_path)
    assert len(blocks) == 3
    assert "CONFIRMADO" in blocks[1] and "RUMORES" in blocks[2]


def test_con_la_bandera_sale_una_seccion_con_etiqueta_por_linea(tmp_path):
    blocks = _report_dos_listas(
        _config(history_name="una-seccion.json", single_section=True),
        [
            _item("Firma oficial del pateador Titán", oficial=True),
            _item("Reporte del partido del domingo Titán", confiable=True),
        ],
        [_item("Rumor de cambio por el receptor Titán", categoria="rumores")],
        tmp_path,
    )
    assert len(blocks) == 2
    seccion = _seccion_equipo(blocks)
    assert seccion.splitlines()[0].startswith("**🏈 EL EQUIPO** (3)")
    renglones = _renglones(seccion)
    assert len(renglones) == 3
    assert renglones[0].startswith("- 🎽 ")
    assert renglones[1].startswith("- ✓ ")
    assert renglones[2].startswith("- 📰 ")
    assert "CONFIRMADO" not in seccion and "RUMORES" not in seccion


def test_la_seccion_unica_anuncia_el_recorte(tmp_path):
    """Con techo de items, el contador dice cuántas historias quedaron fuera."""
    blocks = _report_dos_listas(
        _config(history_name="recorte-unico.json", single_section=True, announce_overflow=True),
        [_item(f"Asunto-{i:04d} relleno que no colapsa") for i in range(12)],
        [],
        tmp_path,
    )
    assert _seccion_equipo(blocks).splitlines()[0].startswith("**🏈 EL EQUIPO** (8 de 12)")


def test_la_seccion_unica_convive_con_la_liga(tmp_path):
    blocks = _report_dos_listas(
        _config_liga(history_name="unica-con-liga.json", single_section=True),
        [_item("Nota del equipo Titán sin repetir")],
        [],
        tmp_path,
    )
    assert len(blocks) == 3
    assert blocks[1].splitlines()[0].startswith("**🏈 LIGA**")
    assert "EL EQUIPO" in blocks[2]


def test_el_canal_de_los_titans_declara_la_seccion_unica():
    from scripts.resumen_rayados_diario import CONFIG as RAYADOS
    from scripts.resumen_tigres_diario import CONFIG as TIGRES
    from scripts.titans_daily import CONFIG as TITANS

    assert TITANS.single_section is True
    assert "TENNESSEE TITANS" in TITANS.team_section_title
    assert RAYADOS.single_section is False
    assert TIGRES.single_section is False


def test_los_rumores_no_desaparecen_cuando_la_seccion_se_llena(tmp_path):
    """Sin reserva, ocho confirmadas dejaban la etiqueta 📰 invisible para siempre."""
    confirmadas = [_item(f"Asunto-{i:04d}-abc relleno que no colapsa") for i in range(12)]
    rumores = [
        _item(f"Rumor-{i:04d}-xyz relleno distinto que no colapsa", categoria="rumores")
        for i in range(3)
    ]
    seccion = _seccion_equipo(
        _report_dos_listas(
            _config(history_name="reserva.json", single_section=True, announce_overflow=True),
            confirmadas,
            rumores,
            tmp_path,
        )
    )
    renglones = _renglones(seccion)
    assert len(renglones) == 8, "el techo sigue siendo 8"
    assert renglones[-1].startswith("- 📰 "), "el rumor del final conserva su hueco"
    assert sum(1 for line in renglones if line.startswith("- 📰 ")) == 2, "un tercio del techo"
    assert seccion.splitlines()[0].startswith("**🏈 EL EQUIPO** (8 de 15)")


# la jornada por feeds directos y el techo por presupuesto (#386)


def _report_jornada(
    config: TeamConfig,
    equipo: list[NewsItem],
    jornada: list[NewsItem],
    tmp_path: Path,
) -> list[str]:
    def fetch_google(query: str, category: str) -> list[NewsItem]:
        return equipo if category == "confirmadas" else []

    def fetch_rss(url: str, source: str, category: str) -> list[NewsItem]:
        return [i for i in jornada if i.category == category]

    return build_report(
        config,
        history_path=str(tmp_path / config.history_name),
        fetch_google_news=fetch_google,
        fetch_official=list,
        enrich_official=lambda found: found,
        fetch_rss=fetch_rss,
    )


def _config_jornada(**overrides) -> TeamConfig:
    return _config(
        extra_section=ExtraSection(
            titulo="**🏈 JORNADA** ({count})",
            categoria="liga",
            feeds=(("FOX Sports", "https://fox.example/rss"),),
        ),
        **overrides,
    )


def _notas_jornada(n: int) -> list[NewsItem]:
    return [
        NewsItem(
            title=f"Jornada-{i:04d} resultado que no colapsa",
            link=f"https://fox.example/nfl/{i}",
            source="FOX Sports",
            confiable=True,
            origin="rss:FOX Sports",
            category="liga",
        )
        for i in range(n)
    ]


def test_la_jornada_sale_de_los_feeds_directos(tmp_path):
    blocks = _report_jornada(
        _config_jornada(history_name="jornada-feeds.json"),
        _notas(1),
        _notas_jornada(3),
        tmp_path,
    )
    jornada = next(b for b in blocks if "JORNADA" in b)
    assert jornada.splitlines()[0].startswith("**🏈 JORNADA** (3)")
    assert "FOX Sports" in jornada
    assert all(line.startswith("- ") for line in jornada.splitlines()[2:])


def test_sin_feeds_ni_query_la_seccion_sale_vacia(tmp_path):
    """Sin fuentes declaradas no hay items: el bloque avisa, no inventa."""
    blocks = _report_jornada(
        _config_jornada(history_name="jornada-vacia.json").__class__(
            **{
                **{
                    k: getattr(_config_jornada(), k) for k in _config_jornada().__dataclass_fields__
                },
                "extra_section": ExtraSection(titulo="**🏈 JORNADA** ({count})"),
                "history_name": "jornada-vacia.json",
            }
        ),
        _notas(1),
        _notas_jornada(3),
        tmp_path,
    )
    jornada = next(b for b in blocks if "JORNADA" in b)
    assert "Sin novedades de la liga" in jornada


def test_sin_techo_el_bloque_llena_el_presupuesto(tmp_path):
    """max_items=None (#386): el techo lo pone el presupuesto del mensaje."""
    notas = [_item(f"Asunto-{i:04d}-abc relleno corto") for i in range(20)]
    blocks = _report(
        _config(history_name="presupuesto.json", max_items=None, announce_overflow=True),
        notas,
        tmp_path,
    )
    seccion = _confirmado(blocks)
    renglones = _renglones(seccion)
    assert len(renglones) > 8, "con techo fijo salían 8"
    assert len(seccion) <= 3000, "el bloque se pasa del presupuesto del mensaje"
    assert seccion.splitlines()[0].startswith("**✅ CONFIRMADO** (20)")


def test_con_techo_declarado_el_recorte_no_cambia(tmp_path):
    """Rayados y Tigres declaran 8: su recorte y su contador siguen igual."""
    blocks = _report(
        _config(history_name="techo-fijo.json", max_items=8, announce_overflow=True),
        [_item(f"Asunto-{i:04d}-abc relleno que no colapsa") for i in range(20)],
        tmp_path,
    )
    seccion = _confirmado(blocks)
    assert len(_renglones(seccion)) == 8
    assert seccion.splitlines()[0].startswith("**✅ CONFIRMADO** (8 de 20)")


# el filtro de titulares que el equipo no quiere ver (#386)


def test_sin_palabras_excluidas_todo_sale_igual(tmp_path):
    """Opt-in: sin `exclude_keywords` un titular de cuotas sale como siempre."""
    notas = [_item("NFL MVP odds: el favorito del ano"), _item("Titans firman a un linebacker")]
    blocks = _report(_config(history_name="sin-filtro.json"), notas, tmp_path)
    seccion = _confirmado(blocks)
    assert "odds" in seccion
    assert seccion.splitlines()[0].startswith("**✅ CONFIRMADO** (2)")


def test_las_palabras_excluidas_se_caen_del_reporte(tmp_path):
    notas = [
        _item("NFL Week 4 early odds: Chiefs road favorites"),
        _item("Use DraftKings promo code to get $150 in bonus bets"),
        _item("Giants star pass rusher tore his ACL against Titans"),
    ]
    blocks = _report(
        _config(history_name="con-filtro.json", exclude_keywords=["odds", "bets"]), notas, tmp_path
    )
    seccion = _confirmado(blocks)
    assert "early odds" not in seccion, "la cuota se cae"
    assert "bonus bets" not in seccion, "el promo de apuestas se cae"
    assert "tore his ACL" in seccion, "la noticia de verdad se queda"
    assert seccion.splitlines()[0].startswith("**✅ CONFIRMADO** (1)")


def test_el_filtro_no_marca_los_items_como_vistos(tmp_path):
    """Lo descartado no es "visto": es ruido, y mañana se vuelve a medir igual."""
    notas = [_item("NFL MVP odds: el favorito del ano"), _item("Titans firman a un linebacker")]
    _report(
        _config(history_name="filtro-historial.json", exclude_keywords=["odds"]),
        notas,
        tmp_path,
    )
    # El historial guarda URLs, no títulos.
    guardado = json.loads((tmp_path / "filtro-historial.json").read_text(encoding="utf-8"))
    assert any("Titans-firman" in url for url in guardado), "la noticia sí se marca vista"
    assert not any("odds" in url.lower() for url in guardado), "el ruido no entra al historial"


def test_el_bloque_nunca_pasa_del_presupuesto(tmp_path):
    """El presupuesto es de la sección montada, no de la estimación.

    Con un límite muy justo la cabecera, el subtítulo y los emojis se llevan
    caracteres que la aritmética no ve; el bloque se suelta titulares hasta
    caber.
    """
    config = _config(
        history_name="presupuesto-exacto.json",
        max_items=None,
        announce_overflow=True,
        telegram_max_chars=400,
    )
    notas = [_item(f"Asunto-{i:04d}-abc relleno que no colapsa") for i in range(10)]
    blocks = _report(config, notas, tmp_path)
    seccion = _confirmado(blocks)
    assert len(seccion) <= 400, f"la sección se pasa: {len(seccion)}c"
    assert len(_renglones(seccion)) >= 1, "alguna línea tiene que salir"
    assert seccion.splitlines()[0].startswith("**✅ CONFIRMADO** (")


def test_primeros_que_caben_mide_utf16():
    """#424: 🛒 = 1 code point y 2 unidades UTF-16: cabe para len() y no entra."""
    from scripts import team_pipeline

    tag_for = lambda item: "✓"  # noqa: E731
    items = [_item("Oferta 🛒 del día")]
    linea = team_pipeline._linea(items[0], tag_for)
    diff = delivery.utf16_len(linea) - len(linea)
    assert diff >= 1
    presupuesto = len(linea) + 1
    assert team_pipeline._primeros_que_caben(items, tag_for, presupuesto) == []
    assert team_pipeline._primeros_que_caben(items, tag_for, presupuesto + diff) == items


def test_section_recorta_por_utf16_no_por_len():
    """#424: el bucle de _section suelta la línea que solo cabía en code points."""
    from scripts import team_pipeline

    tag_for = lambda item: "✓"  # noqa: E731
    items = [_item("Oferta 🛒 del día")]
    config = _config(max_items=None)
    full = team_pipeline._section("**H** ({count})", "*Sub*", items, tag_for, "", config)
    lineas = full.splitlines()
    assert delivery.utf16_len(full) > len(full)
    interno_len = sum(len(linea) + 1 for linea in lineas[2:])
    topado = delivery.utf16_len(lineas[0]) + delivery.utf16_len(lineas[1]) + 2 + interno_len
    recortado = team_pipeline._section(
        "**H** ({count})",
        "*Sub*",
        items,
        tag_for,
        "",
        _config(max_items=None, telegram_max_chars=topado),
    )
    assert "Oferta" not in recortado
