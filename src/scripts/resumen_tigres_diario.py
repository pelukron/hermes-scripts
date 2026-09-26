#!/usr/bin/env python3
"""Resumen diario de Tigres. El ensamble vive en team_pipeline."""

from hermes_common import retry_request
from scripts.team_pipeline import (
    TeamConfig,
    enter,
    expose,
    fetch_tigres_com,
    publish,
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
