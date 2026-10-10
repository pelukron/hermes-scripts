#!/usr/bin/env python3
"""Resumen diario de Rayados. El ensamble vive en team_pipeline."""

import re
from urllib.parse import urljoin

import hermes_common
from hermes_common import news_utils, retry_request
from scripts.team_pipeline import (
    Request,
    TeamConfig,
    build_report,
    enter,
    history_path,
    expose,
    official_error,
    publish,
)

TIMEOUT = 20


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
        error: list = official_error("rayados.com", exc)
        return error


CONFIG = TeamConfig(
    history_name="rayados-history.json",
    queries={
        "confirmadas": '"Rayados de Monterrey" OR "Club de Fútbol Monterrey"',
        "rumores": (
            '"Rayados" AND (fichaje OR rumor OR filtración OR "mercado de pases" '
            "OR transferencia OR lesionado OR baja OR venta)"
        ),
    },
    sitios_oficiales=["rayados.com", "rayados.mx"],
    header_title="⚽ **Rayados de Monterrey — Noticias del día**",
    sources_line="Fuentes: Google News RSS + rayados.com",
    prefilter_official=False,
    announce_overflow=False,
    edition={"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"},
)


def main() -> None:
    publish(
        lambda: build_report(
            CONFIG,
            history_path=history_path(CONFIG),
            fetch_official=lambda: fetch_rayados_com(retry_request),
        ),
        CONFIG.telegram_max_chars,
    )


if __name__ == "__main__":
    enter(main)
