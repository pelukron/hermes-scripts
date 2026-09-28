"""Pipeline único de los resúmenes de equipo.

Rayados y Tigres eligen un TeamConfig. El fetch del sitio oficial, el
historial, la clasificación y el render viven aquí una sola vez.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

import hermes_common
from hermes_common import filter_by_max_age, news_utils, uv_bin

log = logging.getLogger("hermes")

TELEGRAM_MAX_CHARS = 3000
TIMEOUT = 20

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
    extra_section: Optional[ExtraSection] = None


def ensure_news_deps() -> None:
    """Instala feedparser/bs4 si el cron arrancó sin ellas. No-op si ya están."""
    try:
        import bs4  # noqa: F401
        import feedparser  # noqa: F401
    except ModuleNotFoundError:
        uv = uv_bin()
        try:
            subprocess.check_call(
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    sys.executable,
                    "feedparser",
                    "requests",
                    "beautifulsoup4",
                    "lxml",
                ]
            )
        except subprocess.CalledProcessError as exc:
            log.warning("Failed to install runtime deps: %s", exc)
            raise


def fetch_detail(link: str, timeout: int, request: Request, label: str) -> tuple:
    """Fecha y autor de un artículo. `request` es el retry del script (testeable)."""
    try:
        resp = request(link, timeout=timeout, headers=hermes_common.get_headers("default"))
        return news_utils.parse_detail_page(resp.text)
    except Exception as exc:
        log.warning("Detalle %s falló (%s): %s", label, link, exc)
        return None, None


def fetch_rayados_com(request: Request) -> list:
    """Listado de rayados.com. El sitio no publica fecha: published queda None."""
    from bs4 import BeautifulSoup

    items: list[news_utils.NewsItem] = []
    url = "https://rayados.com/es/noticias/lista"
    try:
        resp = request(url, timeout=TIMEOUT, headers=hermes_common.get_headers("default"))
        soup = BeautifulSoup(resp.text, "lxml")
        seen: set[str] = set()
        for li in soup.find_all("li")[:20]:
            anchor = li.find("a", href=re.compile(r"/es/noticias/\d+(/|\?|$)"))
            if not anchor:
                continue
            href = str(anchor.get("href", "")).strip()
            if not href or href in seen:
                continue
            seen.add(href)
            full_link = urljoin(url, href)
            title = ""
            heading = li.find(["h2", "h3", "h4", "h1"])
            if heading:
                title = heading.get_text(strip=True)
            if not title:
                title = str(anchor.get("title", "")).strip()
            if not title or len(title) < 10:
                continue
            if full_link in seen:
                continue
            seen.add(full_link)
            items.append(
                news_utils.NewsItem(
                    title=title,
                    link=full_link,
                    source="rayados.com",
                    oficial=True,
                    confiable=True,
                    rumor=False,
                    origin="rayados.com",
                    category="confirmadas",
                )
            )
        return items
    except Exception as exc:
        return [
            news_utils.NewsItem(
                title=f"[Error rayados.com: {str(exc)[:80]}]",
                source="rayados.com",
                origin="rayados.com",
                category="confirmadas",
            )
        ]


def listing_time_of(link_tag) -> Optional[datetime]:
    """Fecha del <time> en el padre inmediato del <a>. No mira tarjetas vecinas."""
    parent = getattr(link_tag, "parent", None)
    if parent is None:
        return None
    time_tag = parent.find("time")
    if time_tag is None:
        return None
    dt_attr = time_tag.get("datetime", "")
    if dt_attr:
        parsed = hermes_common.parse_published(dt_attr)
        if parsed is not None:
            return parsed
    return news_utils.parse_fecha_es(time_tag.get_text(" ", strip=True))


def _tigres_title(anchor) -> str:
    title = anchor.get_text(" ", strip=True)
    if not title or len(title) < 10:
        title = str(anchor.get("title", "")).strip()
    if not title or len(title) < 10:
        heading = anchor.find_next(["h2", "h3", "h4", "h1"])
        if heading:
            title = heading.get_text(strip=True)
    if not title or len(title) < 10:
        return ""
    title = re.sub(r"^\w+ \d{1,2}, \d{4}\s*", "", title)
    return re.sub(r"\s*Ver más$", "", title).strip()


def _tigres_article(href: str) -> bool:
    path = href.split("?")[0].rstrip("/")
    slug = r"/es/noticias/[^/]+/[^/]+$"
    single = r"/es/noticias/(?!tigres/?$|club/?$|vlogs/?$|page/)[^/]+$"
    if not re.search(slug, path) and not re.search(single, path):
        return False
    cats = r"/es/noticias/(tigres|tigres-femenil|club|impacto-social|vlogs|page/\d+)/?$"
    return re.search(cats, path) is None


def fetch_tigres_com(request: Request) -> list:
    """Listado de tigres.com.mx. La fecha del <time> alimenta el filtro de 48h."""
    from bs4 import BeautifulSoup

    items: list[news_utils.NewsItem] = []
    url = "https://www.tigres.com.mx/es/noticias/"
    try:
        resp = request(url, timeout=TIMEOUT, headers=hermes_common.get_headers("default"))
        soup = BeautifulSoup(resp.text, "lxml")
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=re.compile(r"/es/noticias/.+"))[:40]:
            href = str(anchor.get("href", "")).strip()
            if not href or href in seen or not _tigres_article(href):
                continue
            seen.add(href)
            full_link = urljoin(url, href)
            title = _tigres_title(anchor)
            if not title:
                continue
            if str(full_link).rstrip("/") in {str(item.link).rstrip("/") for item in items}:
                continue
            items.append(
                news_utils.NewsItem(
                    title=title,
                    link=full_link,
                    source="tigres.com.mx",
                    oficial=True,
                    confiable=True,
                    rumor=False,
                    origin="tigres.com.mx",
                    category="confirmadas",
                    published=listing_time_of(anchor),
                )
            )
        return items
    except Exception as exc:
        return [
            news_utils.NewsItem(
                title=f"[Error tigres.com.mx: {str(exc)[:80]}]",
                source="tigres.com.mx",
                origin="tigres.com.mx",
                category="confirmadas",
            )
        ]


def _google_items(config: TeamConfig, fetch_google_news: GoogleFetch) -> list:
    confirmadas = fetch_google_news(config.queries["confirmadas"], "confirmadas")
    time.sleep(1)
    rumores = fetch_google_news(config.queries["rumores"], "rumores")
    time.sleep(1)
    return filter_by_max_age(confirmadas + rumores)


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
    return str(getattr(items[0], "title", "")).startswith("[Error")


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
    """Prefijo de items cuyas líneas caben en el presupuesto de caracteres."""
    mostrados: list = []
    usado = 0
    for item in items:
        largo = len(_linea(item, tag_for)) + 1
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
    hueco = sum(len(_linea(i, tag_for)) + 1 for i in reservados)
    cabeza = items[: len(items) - cola]
    return _primeros_que_caben(cabeza, tag_for, max(limite - hueco, 0)) + reservados


def _section(
    heading: str,
    subtitle: str,
    items: list,
    tag_for: Callable[[news_utils.NewsItem], str],
    empty: str,
    config: TeamConfig,
    reserve: int = 0,
) -> str:
    """Bloque de Telegram de una sección.

    El presupuesto de las líneas descuenta la cabecera y el subtítulo, y se
    calcula con el contador más largo posible: el `{count}` real nunca ocupa
    más, así que el bloque no puede pasarse del presupuesto por un dígito.
    """
    cabecera = heading.format(count=_count_label(items, items, config.announce_overflow))
    limite = config.telegram_max_chars - len(cabecera) - len(subtitle) - 2
    shown = _showed(items, tag_for, config, limite, reserve)
    lines = [
        heading.format(count=_count_label(items, shown, config.announce_overflow)),
        subtitle,
    ]
    if not shown:
        lines.append(empty)
        return "\n".join(lines)
    for item in shown:
        lines.append(news_utils.format_item_line(tag_for(item), item, item.link))
    return "\n".join(lines)


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


def build_report(
    config: TeamConfig,
    *,
    history_path: str,
    fetch_google_news: GoogleFetch,
    fetch_official: OfficialFetch,
    enrich_official: Enrich,
    fetch_rss: RssFetch = news_utils.fetch_rss_feed,
) -> list[str]:
    """Ensambla los bloques de Telegram para un equipo.

    Sin `extra_section` sale lo de siempre (header + CONFIRMADO + RUMORES). Con
    ella, la liga viaja en el mismo historial y la misma clasificación, pero se
    parte a su bloque propio antes del render: el dedupe por título corre sobre
    los tres juntos y nada sale repetido entre liga y equipo.
    """
    google = _google_items(config, fetch_google_news)
    official = _official_items(config, fetch_official, enrich_official)
    extra = _extra_items(config, fetch_google_news, fetch_rss)
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


_REEXPORTS = (
    "NewsItem",
    "build_google_news_url",
    "canonical_title",
    "clean_title",
    "clean_url",
    "dedupe",
    "dedupe_by_title",
    "domain_of",
    "enrich_from_detail",
    "format_item_line",
    "normalize",
    "normalize_urls",
    "now_str",
    "parse_detail_page",
    "parse_fecha_es",
    "resolve_url",
    "title_similar",
)


def expose(
    ns: dict[str, Any],
    config: TeamConfig,
    *,
    request: Request,
    official_impl: Callable[[Request], list],
    detail_label: str,
    official_name: str,
    detail_name: str,
    enrich_name: str,
) -> None:
    """Cuelga en el script los nombres que los tests parchean, sin copiar el ensamble."""
    ns["retry_request"] = request
    ns["QUERIES"] = config.queries
    ns["SITIOS_OFICIALES"] = config.sitios_oficiales
    ns["SITIOS_CONFIABLES"] = config.sitios_confiables
    ns["RUMOR_KEYWORDS"] = config.rumor_keywords
    ns["TELEGRAM_MAX_CHARS"] = config.telegram_max_chars
    ns["MAX_ITEMS_POR_SECCION"] = config.max_items
    for name in _REEXPORTS:
        ns[name] = getattr(news_utils, name)
    ensure_news_deps()
    import feedparser

    ns["feedparser"] = feedparser

    def is_oficial(url: str) -> bool:
        return news_utils.is_oficial(url, config.sitios_oficiales)

    def is_confiable_by_url(url: str) -> bool:
        return news_utils.is_confiable_by_url(
            url, config.sitios_oficiales, config.sitios_confiables
        )

    def is_confiable(source: str, url: str) -> bool:
        return news_utils.is_confiable(
            source, url, config.sitios_oficiales, config.sitios_confiables
        )

    def smells_like_rumor(title: str) -> bool:
        return news_utils.smells_like_rumor(title, config.rumor_keywords)

    def fetch_google_news(query: str, category: str) -> list:
        return news_utils.fetch_google_news(
            query,
            category,
            config.sitios_oficiales,
            config.sitios_confiables,
            config.rumor_keywords,
            config.edition,
        )

    def fetch_rss(url: str, source: str, category: str) -> list:
        return news_utils.fetch_rss_feed(
            url,
            source,
            category,
            config.sitios_oficiales,
            config.sitios_confiables,
            config.rumor_keywords,
        )

    def fetch_official() -> list:
        return official_impl(ns["retry_request"])

    def fetch_one(link: str, timeout: int = 10) -> tuple:
        return fetch_detail(link, timeout, ns["retry_request"], detail_label)

    def enrich(items: list, max_details: int = 12) -> list:
        return news_utils.enrich_from_detail(items, ns[detail_name], max_details)

    def classify(all_items: list) -> tuple:
        return news_utils.classify(all_items, config.sitios_oficiales, config.sitios_confiables)

    def historial_path() -> str:
        return str(hermes_common.state_dir() / config.history_name)

    def build_report_blocks() -> list[str]:
        return build_report(
            config,
            history_path=ns["historial_path"](),
            fetch_google_news=ns["fetch_google_news"],
            fetch_official=ns[official_name],
            enrich_official=ns[enrich_name],
            fetch_rss=ns["fetch_rss"],
        )

    ns["is_oficial"] = is_oficial
    ns["is_confiable_by_url"] = is_confiable_by_url
    ns["is_confiable"] = is_confiable
    ns["smells_like_rumor"] = smells_like_rumor
    ns["fetch_google_news"] = fetch_google_news
    ns["fetch_rss"] = fetch_rss
    ns[official_name] = fetch_official
    ns[detail_name] = fetch_one
    ns[enrich_name] = enrich
    ns["classify"] = classify
    ns["historial_path"] = historial_path
    ns["build_report_blocks"] = build_report_blocks


def fit_block(block: str, limit: int = TELEGRAM_MAX_CHARS) -> str:
    """Recorta por línea entera. Un corte a media URL llega al chat como texto plano."""
    if len(block) <= limit:
        return block
    kept: list[str] = []
    size = 0
    for line in block.splitlines():
        extra = len(line) + (1 if kept else 0)
        if size + extra > limit:
            break
        kept.append(line)
        size += extra
    return "\n".join(kept)


def publish(blocks_fn: Callable[[], list[str]], limit: int = TELEGRAM_MAX_CHARS) -> None:
    """Imprime cada bloque separado por `---` para el gateway de Telegram."""
    hermes_common.setup_logging()
    for block in blocks_fn():
        log.info(fit_block(block, limit))
        log.info("\n---\n")
        time.sleep(1.5)


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
