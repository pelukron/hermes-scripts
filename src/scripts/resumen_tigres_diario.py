#!/usr/bin/env python3
"""Resumen diario de Tigres. El ensamble vive en team_pipeline."""

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
    fetch_tigres_com as _fetch_tigres_com,
)

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
)

QUERIES = CONFIG.queries
SITIOS_OFICIALES = CONFIG.sitios_oficiales
TELEGRAM_MAX_CHARS = CONFIG.telegram_max_chars
MAX_ITEMS_POR_SECCION = CONFIG.max_items


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
    "enrich_from_detail",
    "format_item_line",
    "NewsItem",
    "normalize",
    "normalize_urls",
    "now_str",
    "parse_detail_page",
    "parse_fecha_es",
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


def fetch_tigres_com():
    return _fetch_tigres_com(retry_request)


def fetch_tigres_detail(link: str, timeout: int = 10):
    return fetch_detail(link, timeout, retry_request, "tigres.com.mx")


def enrich_tigres_items(items: list, max_details: int = 12) -> list:
    return news_utils.enrich_from_detail(items, fetch_tigres_detail, max_details)


def classify(all_items: list) -> tuple:
    return news_utils.classify(all_items, SITIOS_OFICIALES, SITIOS_CONFIABLES)


def historial_path() -> str:
    return str(hermes_common.state_dir() / CONFIG.history_name)


def build_report_blocks():
    return build_report(
        CONFIG,
        history_path=historial_path(),
        fetch_google_news=fetch_google_news,
        fetch_official=fetch_tigres_com,
        enrich_official=enrich_tigres_items,
    )


def main() -> None:
    publish(build_report_blocks, TELEGRAM_MAX_CHARS)


if __name__ == "__main__":
    enter(main)
