#!/usr/bin/env python3
"""Resumen diario de Rayados. El ensamble vive en team_pipeline."""

import hermes_common
from hermes_common import news_utils, retry_request
from scripts.team_pipeline import (
    RUMOR_KEYWORDS,
    SITIOS_CONFIABLES,
    TeamConfig,
    build_report,
    ensure_news_deps,
    enter,
    fetch_detail,
    publish,
)
from scripts.team_pipeline import (
    fetch_rayados_com as _fetch_rayados_com,
)

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
)

QUERIES = CONFIG.queries
SITIOS_OFICIALES = CONFIG.sitios_oficiales
TELEGRAM_MAX_CHARS = CONFIG.telegram_max_chars


def _load_feedparser():
    ensure_news_deps()
    import feedparser

    return feedparser


feedparser = _load_feedparser()

for _name in (
    "build_google_news_url",
    "canonical_title",
    "clean_title",
    "clean_url",
    "dedupe",
    "dedupe_by_title",
    "domain_of",
    "format_item_line",
    "NewsItem",
    "normalize",
    "normalize_urls",
    "now_str",
    "resolve_url",
    "title_similar",
):
    globals()[_name] = getattr(news_utils, _name)


def is_oficial(url: str) -> bool:
    return news_utils.is_oficial(url, SITIOS_OFICIALES)


def is_confiable_by_url(url: str) -> bool:
    return news_utils.is_confiable_by_url(url, SITIOS_OFICIALES, SITIOS_CONFIABLES)


def is_confiable(source: str, url: str) -> bool:
    return news_utils.is_confiable(source, url, SITIOS_OFICIALES, SITIOS_CONFIABLES)


def smells_like_rumor(title: str) -> bool:
    return news_utils.smells_like_rumor(title, RUMOR_KEYWORDS)


def fetch_google_news(query: str, category: str) -> list:
    return news_utils.fetch_google_news(
        query, category, SITIOS_OFICIALES, SITIOS_CONFIABLES, RUMOR_KEYWORDS
    )


def fetch_rayados_com():
    return _fetch_rayados_com(retry_request)


def fetch_rayados_detail(link: str, timeout: int = 10):
    return fetch_detail(link, timeout, retry_request, "rayados.com")


def enrich_rayados_items(items: list, max_details: int = 12) -> list:
    return news_utils.enrich_from_detail(items, fetch_rayados_detail, max_details)


def classify(all_items: list) -> tuple:
    return news_utils.classify(all_items, SITIOS_OFICIALES, SITIOS_CONFIABLES)


def historial_path() -> str:
    return str(hermes_common.state_dir() / CONFIG.history_name)


def build_report_blocks():
    return build_report(
        CONFIG,
        history_path=historial_path(),
        fetch_google_news=fetch_google_news,
        fetch_official=fetch_rayados_com,
        enrich_official=enrich_rayados_items,
    )


def main() -> None:
    publish(build_report_blocks, TELEGRAM_MAX_CHARS)


if __name__ == "__main__":
    enter(main)
