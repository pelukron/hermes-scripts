#!/usr/bin/env python3
"""Resumen diario de Tigres. El ensamble vive en team_pipeline."""

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import hermes_common
from hermes_common import news_utils, retry_request
from scripts.team_pipeline import (
    Request,
    TeamConfig,
    enter,
    expose,
    publish,
)

TIMEOUT = 20


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


# La query abre con frase citada. AND y paréntesis dejan el feed en 0 entries.
CONFIG = TeamConfig(
    history_name="tigres-history.json",
    queries={
        "confirmadas": '"Tigres UANL" OR "Club Tigres" OR "Tigres de Monterrey"',
        "rumores": ('"Tigres UANL" fichaje OR "Tigres UANL" refuerzo OR "Tigres UANL" lesion'),
    },
    sitios_oficiales=["tigres.com.mx"],
    header_title="🐯 **Tigres UANL — Noticias del día**",
    sources_line="Fuentes: Google News RSS + tigres.com.mx",
    prefilter_official=True,
    announce_overflow=True,
    edition={"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"},
)

expose(
    globals(),
    CONFIG,
    request=retry_request,
    official_impl=fetch_tigres_com,
    detail_label="tigres.com.mx",
    official_name="fetch_tigres_com",
    detail_name="fetch_tigres_detail",
    enrich_name="enrich_tigres_items",
)


def main() -> None:
    publish(globals()["build_report_blocks"], CONFIG.telegram_max_chars)


if __name__ == "__main__":
    enter(main)
