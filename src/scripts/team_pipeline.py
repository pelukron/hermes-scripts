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
OfficialFetch = Callable[[], list]
Enrich = Callable[[list], list]
Request = Callable[..., Any]


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
    max_items: int = 8
    telegram_max_chars: int = TELEGRAM_MAX_CHARS
    sitios_confiables: list[str] = field(default_factory=lambda: list(SITIOS_CONFIABLES))
    rumor_keywords: list[str] = field(default_factory=lambda: list(RUMOR_KEYWORDS))


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


def _section(
    heading: str,
    subtitle: str,
    items: list,
    tag_for: Callable[[news_utils.NewsItem], str],
    empty: str,
    config: TeamConfig,
) -> str:
    shown = items[: config.max_items]
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


def _render(config: TeamConfig, confirmadas: list, rumores: list) -> list[str]:
    header = "\n".join(
        [
            config.header_title,
            f"_Actualizado: {news_utils.now_str()}_",
            hermes_common.version_footer(),
            config.sources_line,
        ]
    )
    confirmed = _section(
        "**✅ CONFIRMADO** ({count})",
        "_Fuentes oficiales y medios establecidos_",
        confirmadas,
        _tag_confirmada,
        "_No se encontraron noticias confirmadas nuevas en las últimas 48h._\n",
        config,
    )
    rumors = _section(
        "**⚠️ RUMORES** ({count})",
        "_No confirmado oficialmente. Tomar con discreción_",
        rumores,
        _tag_rumor,
        "_No se encontraron rumores o filtraciones nuevos en las últimas 48h._\n",
        config,
    )
    return [header, confirmed, rumors]


def build_report(
    config: TeamConfig,
    *,
    history_path: str,
    fetch_google_news: GoogleFetch,
    fetch_official: OfficialFetch,
    enrich_official: Enrich,
) -> list[str]:
    """Ensambla los tres bloques de Telegram para un equipo."""
    google = _google_items(config, fetch_google_news)
    official = _official_items(config, fetch_official, enrich_official)
    kept = _without_history(history_path, google + official)
    confirmadas, rumores = news_utils.classify(
        kept, config.sitios_oficiales, config.sitios_confiables
    )
    return _render(
        config,
        news_utils.dedupe_by_title(confirmadas),
        news_utils.dedupe_by_title(rumores),
    )


def publish(blocks_fn: Callable[[], list[str]], limit: int = TELEGRAM_MAX_CHARS) -> None:
    """Imprime cada bloque separado por `---` para el gateway de Telegram."""
    hermes_common.setup_logging()
    for block in blocks_fn():
        log.info(hermes_common.smart_truncate(block, limit=limit))
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
