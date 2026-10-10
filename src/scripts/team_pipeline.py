"""Pipeline único de los resúmenes de equipo.

Cada equipo elige un TeamConfig y posee su fetcher oficial. El historial,
la clasificación y el render viven aquí una sola vez.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

import hermes_common
from hermes_common import delivery, filter_by_max_age, news_utils, retry_request

log = logging.getLogger("hermes")

# Per-message budget for this area, tighter than the sender hard cap (4096).
# The number is area policy (ADR 0009). The section decides which item lines fit
# and declares that cut. ``delivery.emit`` still enforces the budget: it drops a
# line that cannot be shown and does not restate a cut the heading already declared.
TELEGRAM_MAX_CHARS = 3000

# Medios y keywords idénticos en ambos equipos: una sola copia.
SITIOS_CONFIABLES: list[str] = [
    "milenio.com",
    "elsoldemonterrey.com.mx",
    "marca.com",
    "espn.com.mx",
    "mediotiempo.com",
    "record.com.mx",
    "tudn.com",
    "foxdeportes.com",
    "tvazteca.com",
    "lineadirectaportal.com",
    "eluniversal.com.mx",
    "reforma.com",
    "jornada.com.mx",
    "elporvenir.com.mx",
    "rg.sport",
    "onefootball.com",
    "as.com",
    "espndeportes.espn.com",
    "deportes.televisa.com",
    "aztecadeportes.com",
    "sopitas.com",
    "cancunmio.com",
]

RUMOR_KEYWORDS: list[str] = [
    "rumor",
    "filtr",
    "filtran",
    "apunta",
    "podría",
    "interesado",
    "interesa",
    "oferta",
    "negocia",
    "negociaciones",
    "cerca de",
    "a un paso",
    "sondea",
    "sondeo",
    "pretende",
    "busca",
    "quiere",
    "vinculado",
    "en la mira",
    "mercado de pases",
    "fichaje",
    "refuerzo",
    "baja",
    "lesionado",
]

GoogleFetch = Callable[[str, str], list]
RssFetch = Callable[..., list]
OfficialFetch = Callable[[], list]
Enrich = Callable[[list], list]
Request = Callable[..., Any]


@dataclass(frozen=True)
class ExtraSection:
    """Sección opcional de contexto (liga) con bloque propio en el reporte.

    El `titulo` lleva `{count}` (lo rellena `_section`); la `query` abre con
    frase citada, igual que `queries` (AND y paréntesis dejan el feed en 0);
    la `categoria` etiqueta los NewsItem para el fetch.

    `feeds` son feeds RSS propios — `(nombre, url)` — para las fuentes que no
    pasan por Google News: sus enlaces son tres veces más cortos, así que caben
    tres veces más titulares por mensaje (#386). La sección puede venir de
    `feeds`, de `query` o de las dos cosas; sin ninguna de las dos no hay items.
    """

    titulo: str
    query: str = ""
    categoria: str = "confirmadas"
    feeds: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TeamConfig:
    """Lo que cambia entre equipos. El resto del reporte no se copia."""

    history_name: str
    queries: dict[str, str]
    sitios_oficiales: list[str]
    header_title: str
    sources_line: str
    prefilter_official: bool
    announce_overflow: bool
    edition: dict[str, str]
    # Techo de líneas por sección. `None` = lo fija el presupuesto del mensaje
    # (`telegram_max_chars`), que es lo que pide #386 para el canal: más
    # titulares por mensaje sin romper el contrato de 1 mensaje = 1 trozo.
    max_items: Optional[int] = 8
    # Colapsa la misma historia contada por varios medios (#386). Opt-in: sin
    # declararla, el reporte sale igual que siempre (Rayados y Tigres).
    dedupe_story: bool = False
    # Una sola sección del equipo con etiqueta por línea (🎽/✓/📰) en vez de los
    # bloques CONFIRMADO + RUMORES (#386). Opt-in; `team_section_title` lleva
    # `{count}` igual que el título de `extra_section`.
    single_section: bool = False
    team_section_title: str = "**🏈 EL EQUIPO** ({count})"
    telegram_max_chars: int = TELEGRAM_MAX_CHARS
    sitios_confiables: list[str] = field(default_factory=lambda: list(SITIOS_CONFIABLES))
    rumor_keywords: list[str] = field(default_factory=lambda: list(RUMOR_KEYWORDS))
    # Titulares que el equipo no quiere ver, por palabra en el título (#386).
    # En los feeds directos el medio publica la previa y la cuota a la vez, así
    # que se cae la línea, no la fuente. Opt-in y vacío por defecto: Rayados y
    # Tigres no cambian.
    exclude_keywords: list[str] = field(default_factory=list)
    extra_section: Optional[ExtraSection] = None


def fetch_detail(link: str, timeout: int, request: Request, label: str) -> tuple:
    """Fecha y autor de un artículo. `request` es el retry del script (testeable)."""
    try:
        resp = request(link, timeout=timeout, headers=hermes_common.get_headers("default"))
        return news_utils.parse_detail_page(resp.text)
    except Exception as exc:
        log.warning("Detalle %s falló (%s): %s", label, link, exc)
        return None, None


def _google_items(config: TeamConfig, fetch_google_news: GoogleFetch) -> list:
    confirmadas = fetch_google_news(config.queries["confirmadas"], "confirmadas")
    time.sleep(1)
    rumores = fetch_google_news(config.queries["rumores"], "rumores")
    time.sleep(1)
    return filter_by_max_age(confirmadas + rumores)


def _sin_ruido(items: list, config: TeamConfig) -> list:
    """Descarta los titulares que el equipo no quiere ver (apuestas, sobre todo).

    Filtra por título, no por fuente: el medio que publica la previa publica
    también la cuota, y lo que se cae es la línea. Se aplica antes del historial
    porque estos items no son "vistos": son ruido que no se va a mostrar nunca.
    """
    if not config.exclude_keywords:
        return items
    patron = re.compile("|".join(re.escape(k) for k in config.exclude_keywords), re.IGNORECASE)
    return [i for i in items if not patron.search(i.title)]


def _extra_items(config: TeamConfig, fetch_google_news: GoogleFetch, fetch_rss: RssFetch) -> list:
    """Los items de la sección de liga. Vacío si el equipo no la declara.

    Las fuentes directas van primero: son las que traen las novedades de la
    jornada con enlaces cortos, y `_section` llena el bloque en orden.
    """
    if config.extra_section is None:
        return []
    seccion = config.extra_section
    items: list = []
    for nombre, url in seccion.feeds:
        items += fetch_rss(url, nombre, seccion.categoria)
        time.sleep(1)
    if seccion.query:
        items += fetch_google_news(seccion.query, seccion.categoria)
        time.sleep(1)
    return filter_by_max_age(items)


def _official_items(
    config: TeamConfig, fetch_official: OfficialFetch, enrich_official: Enrich
) -> list:
    items = fetch_official()
    if _official_failed(items):
        return []
    if config.prefilter_official:
        items = filter_by_max_age(items, missing="drop")
    enrich_official(items)
    return filter_by_max_age(items, missing="drop")


def _official_failed(items: list) -> bool:
    if len(items) != 1:
        return False
    return str(getattr(items[0], "title", "")).startswith(ERROR_TITLE_PREFIX)


ERROR_TITLE_PREFIX = "[Error"
"""Single owner of the official-fetcher failure sentinel (#431)."""


def official_error(source: str, exc: Exception) -> list[news_utils.NewsItem]:
    """Error item for a failed official fetch, built by the pipeline.

    Same shape the scripts used to build by hand: prefixed title with the
    message cut at 80 chars, `confirmadas` category. `_official_failed`
    recognizes exactly these items.
    """
    return [
        news_utils.NewsItem(
            title=f"{ERROR_TITLE_PREFIX} {source}: {str(exc)[:80]}",
            source=source,
            origin=source,
            category="confirmadas",
        )
    ]


def _without_history(history_path: str, items: list) -> list:
    history = hermes_common.HistoryManager(history_path, ttl_hours=72)
    filtered: list = []
    for item in items:
        link = item.link
        if link:
            link = news_utils.clean_url(link)
            item.link = link
        if link and history.exists(link):
            continue
        filtered.append(item)
        if link:
            history.add(link)
    return filtered


def _count_label(items: list, shown: list, announce: bool) -> str:
    if not announce:
        return str(len(items))
    extra = f" de {len(items)}" if len(items) > len(shown) else ""
    return f"{len(shown)}{extra}"


def _tag_confirmada(item: news_utils.NewsItem) -> str:
    return "🎽" if item.oficial else "✓"


def _tag_rumor(item: news_utils.NewsItem) -> str:
    return "📰"


def _tag_equipo(item: news_utils.NewsItem) -> str:
    """Etiqueta por línea de la sección única: oficial, confirmado o rumor.

    Usa los mismos criterios que `news_utils.classify` para mandar un item a
    rumores (categoría de la consulta o título que huele a rumor): si divergen,
    la etiqueta diría una cosa y la lista otra.
    """
    if item.oficial:
        return "🎽"
    if item.category == "rumores" or item.rumor:
        return "📰"
    return "✓"


def _linea(item: news_utils.NewsItem, tag_for: Callable[[news_utils.NewsItem], str]) -> str:
    return news_utils.format_item_line(tag_for(item), item, item.link)


def _primeros_que_caben(
    items: list, tag_for: Callable[[news_utils.NewsItem], str], presupuesto: int
) -> list:
    """Prefijo de items cuyas líneas caben en el presupuesto, medido en UTF-16 (#424)."""
    mostrados: list = []
    usado = 0
    for item in items:
        largo = delivery.utf16_len(_linea(item, tag_for)) + 1
        if usado + largo > presupuesto:
            break
        mostrados.append(item)
        usado += largo
    return mostrados


def _showed(
    items: list,
    tag_for: Callable[[news_utils.NewsItem], str],
    config: TeamConfig,
    limite: int,
    reserve: int = 0,
) -> list:
    """Las líneas que salen en la sección.

    Con `max_items` declarado manda ese techo; con `max_items=None` manda el
    presupuesto del mensaje, que es lo que el canal de los Titans pide: más
    titulares por mensaje sin romper el 1 mensaje = 1 trozo (ADR 0005).

    `reserve` (los rumores del final de la lista) se queda con hasta un tercio
    de las líneas: sin ese hueco, un bloque lleno de confirmadas dejaba la
    etiqueta 📰 invisible para siempre.
    """
    if config.max_items is not None:
        techo = config.max_items
        cola = min(reserve, techo // 3) if reserve else 0
        if cola and len(items) > techo:
            return items[: techo - cola] + items[-cola:]
        return items[:techo]
    mostrados = _primeros_que_caben(items, tag_for, limite)
    if not reserve or len(mostrados) >= len(items):
        return mostrados
    cola = min(reserve, len(mostrados) // 3)
    if not cola:
        return mostrados
    reservados = items[-cola:]
    hueco = sum(delivery.utf16_len(_linea(i, tag_for)) + 1 for i in reservados)
    cabeza = items[: len(items) - cola]
    return _primeros_que_caben(cabeza, tag_for, max(limite - hueco, 0)) + reservados


def _overflow_note(omitted: int) -> str:
    """The cut declaration. Same text as ``delivery._note``."""
    return f"… +{omitted} fuera"


def _bloque(
    heading: str,
    subtitle: str,
    items: list,
    shown: list,
    tag_for: Callable[[news_utils.NewsItem], str],
    config: TeamConfig,
    empty: str = "",
) -> str:
    """One Telegram block for a section whose lines are already chosen.

    The empty copy is only for a list that arrived empty. When items existed
    and none fit, the body is the cut note and nothing else.
    """
    lines = [
        heading.format(count=_count_label(items, shown, config.announce_overflow)),
        subtitle,
    ]
    if shown:
        lines += [news_utils.format_item_line(tag_for(i), i, i.link) for i in shown]
    elif items:
        lines.append(_overflow_note(len(items) - len(shown)))
    else:
        lines.append(empty)
    return "\n".join(lines)


def _reserved_ids(items: list, reserve: int) -> set[int]:
    """Ids of the tail kept until no other shown item can be dropped."""
    if reserve <= 0:
        return set()
    return {id(item) for item in items[-reserve:]}


def _drop_expendable(shown: list, reserved_ids: set[int]) -> None:
    """Drop the last shown item that is not reserved. The tail goes last."""
    for index in range(len(shown) - 1, -1, -1):
        if id(shown[index]) not in reserved_ids:
            del shown[index]
            return
    shown.pop()


def _section(
    heading: str,
    subtitle: str,
    items: list,
    tag_for: Callable[[news_utils.NewsItem], str],
    empty: str,
    config: TeamConfig,
    reserve: int = 0,
) -> str:
    """One Telegram block for a section.

    The budget is estimated without the heading and subtitle, using the longest
    count, then checked on the assembled block. The estimate undershoots emojis
    and the real count, and the message budget is a delivery rule.

    ``max_items`` applies first. After that, non-reserved items drop from the
    end; the reserved tail goes only when nothing else remains. A last line that
    still does not fit is omitted. The cut note is the body only when items
    existed and none are shown.
    """
    cabecera = heading.format(count=_count_label(items, items, config.announce_overflow))
    limite = (
        config.telegram_max_chars - delivery.utf16_len(cabecera) - delivery.utf16_len(subtitle) - 2
    )
    shown = _showed(items, tag_for, config, limite, reserve)
    reserved_ids = _reserved_ids(items, reserve)
    bloque = _bloque(heading, subtitle, items, shown, tag_for, config, empty)
    while delivery.utf16_len(bloque) > config.telegram_max_chars and shown:
        _drop_expendable(shown, reserved_ids)
        bloque = _bloque(heading, subtitle, items, shown, tag_for, config, empty)
    return bloque


def _render(
    config: TeamConfig,
    confirmadas: list,
    rumores: list,
    liga: list | None = None,
) -> list[str]:
    header = "\n".join(
        [
            config.header_title,
            f"*Actualizado: {news_utils.now_str()}*",
            hermes_common.version_footer(),
            config.sources_line,
        ]
    )
    bloques = [header]
    vistos: set[str] = set()
    if liga is not None and config.extra_section is not None:
        liga = news_utils.dedupe_by_title(liga)
        vistos = {news_utils.canonical_title(i.title) for i in liga}
        bloques.append(
            _section(
                config.extra_section.titulo,
                "*Contexto de la liga*",
                liga,
                _tag_confirmada,
                "*Sin novedades de la liga en las últimas 48h.*\n",
                config,
            )
        )
    confirmadas = [
        i
        for i in news_utils.dedupe_by_title(confirmadas)
        if news_utils.canonical_title(i.title) not in vistos
    ]
    rumores = [
        i
        for i in news_utils.dedupe_by_title(rumores)
        if news_utils.canonical_title(i.title) not in vistos
    ]
    if config.single_section:
        # Una sola sección del equipo (#386): las confirmadas primero y los
        # rumores al final, cada línea con su etiqueta. Sale un bloque en vez de
        # dos, así que el presupuesto del mensaje se gasta en contenido.
        bloques.append(
            _section(
                config.team_section_title,
                "*🎽 oficial · ✓ confirmado · 📰 rumor*",
                confirmadas + rumores,
                _tag_equipo,
                "*No se encontraron noticias del equipo en las últimas 48h.*\n",
                config,
                reserve=len(rumores),
            )
        )
        return bloques
    bloques.append(
        _section(
            "**✅ CONFIRMADO** ({count})",
            "*Fuentes oficiales y medios establecidos*",
            confirmadas,
            _tag_confirmada,
            "*No se encontraron noticias confirmadas nuevas en las últimas 48h.*\n",
            config,
        )
    )
    bloques.append(
        _section(
            "**⚠️ RUMORES** ({count})",
            "*No confirmado oficialmente. Tomar con discreción*",
            rumores,
            _tag_rumor,
            "*No se encontraron rumores o filtraciones nuevos en las últimas 48h.*\n",
            config,
        )
    )
    return bloques


def history_path(config: TeamConfig) -> str:
    """State file for this team, resolved when the report runs."""
    return str(hermes_common.state_dir() / config.history_name)


def google_news_for(config: TeamConfig) -> GoogleFetch:
    """Google News fetch bound to this team's sites, keywords, and edition."""

    def fetch(query: str, category: str) -> list:
        return news_utils.fetch_google_news(
            query,
            category,
            config.sitios_oficiales,
            config.sitios_confiables,
            config.rumor_keywords,
            config.edition,
        )

    return fetch


def rss_for(config: TeamConfig) -> RssFetch:
    """Direct RSS fetch bound to this team's sites and rumor keywords."""

    def fetch(url: str, source: str, category: str) -> list:
        return news_utils.fetch_rss_feed(
            url,
            source,
            category,
            config.sitios_oficiales,
            config.sitios_confiables,
            config.rumor_keywords,
        )

    return fetch


def enrich_for(config: TeamConfig) -> Enrich:
    """Detail enrichment with the shared retry and the team's official site."""
    label = config.sitios_oficiales[0] if config.sitios_oficiales else "oficial"

    def fetch_one(link: str, timeout: int = 10) -> tuple:
        return fetch_detail(link, timeout, retry_request, label)

    def enrich(items: list) -> list:
        return news_utils.enrich_from_detail(items, fetch_one)

    return enrich


def build_report(
    config: TeamConfig,
    *,
    history_path: str,
    fetch_official: OfficialFetch,
    fetch_google_news: Optional[GoogleFetch] = None,
    enrich_official: Optional[Enrich] = None,
    fetch_rss: Optional[RssFetch] = None,
) -> list[str]:
    """Ensambla los bloques de Telegram para un equipo.

    Sin `extra_section` sale lo de siempre (header + CONFIRMADO + RUMORES). Con
    ella, la liga viaja en el mismo historial y la misma clasificación, pero se
    parte a su bloque propio antes del render: el dedupe por título corre sobre
    los tres juntos y nada sale repetido entre liga y equipo.

    Google News, the direct feeds, and detail enrichment bind to ``config``
    when the caller does not pass them. The official fetcher stays with the
    team script.
    """
    if fetch_google_news is None:
        fetch_google_news = google_news_for(config)
    if enrich_official is None:
        enrich_official = enrich_for(config)
    if fetch_rss is None:
        fetch_rss = rss_for(config)
    google = _sin_ruido(_google_items(config, fetch_google_news), config)
    official = _sin_ruido(_official_items(config, fetch_official, enrich_official), config)
    extra = _sin_ruido(_extra_items(config, fetch_google_news, fetch_rss), config)
    kept = _without_history(history_path, google + official + extra)
    # El dedupe va después del historial a propósito: así los duplicados que
    # descarta ya quedaron marcados como vistos y no vuelven mañana a pelearse
    # el mismo hueco (#386).
    if config.dedupe_story:
        kept = news_utils.dedupe_by_story(kept)
    confirmadas, rumores = news_utils.classify(
        kept, config.sitios_oficiales, config.sitios_confiables
    )
    if config.extra_section is None:
        return _render(config, confirmadas, rumores)
    enlaces_liga = {i.link for i in extra}
    liga = [i for i in confirmadas + rumores if i.link in enlaces_liga]
    confirmadas = [i for i in confirmadas if i.link not in enlaces_liga]
    rumores = [i for i in rumores if i.link not in enlaces_liga]
    return _render(config, confirmadas, rumores, liga=liga)


def publish(blocks_fn: Callable[[], list[str]], limit: int = TELEGRAM_MAX_CHARS) -> None:
    """Emit each block through the delivery seam: one block, one message.

    The section already chose which items fit. ``delivery.emit`` still drops a
    whole line that does not fit, so a URL is never cut in half, and it does not
    restate a cut the heading already declared.
    """
    hermes_common.setup_logging()
    delivery.emit(blocks_fn(), write=log.info, message_budget=limit)


def enter(main: Callable[[], None]) -> None:
    """Punto de entrada de los scripts: convierte cualquier fallo en exit code."""
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
    raise SystemExit(0)
