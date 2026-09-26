#!/usr/bin/env python3
"""Resumen diario de Rayados. El ensamble vive en team_pipeline."""

from hermes_common import retry_request
from scripts.team_pipeline import (
    TeamConfig,
    enter,
    expose,
    fetch_rayados_com,
    publish,
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

expose(
    globals(),
    CONFIG,
    request=retry_request,
    official_impl=fetch_rayados_com,
    detail_label="rayados.com",
    official_name="fetch_rayados_com",
    detail_name="fetch_rayados_detail",
    enrich_name="enrich_rayados_items",
)


def main() -> None:
    publish(globals()["build_report_blocks"], CONFIG.telegram_max_chars)


if __name__ == "__main__":
    enter(main)
