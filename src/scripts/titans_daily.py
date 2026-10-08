#!/usr/bin/env python3
"""Reporte diario de Tennessee Titans. El ensamble vive en team_pipeline."""

from hermes_common import retry_request
from scripts.team_pipeline import (
    ExtraSection,
    Request,
    TeamConfig,
    build_report,
    enter,
    history_path,
    publish,
)

# La query abre con frase citada. AND y paréntesis dejan el feed en 0 entries.
CONFIG = TeamConfig(
    history_name="titans-history.json",
    queries={
        "confirmadas": '"Tennessee Titans" OR "Titans NFL"',
        "rumores": (
            '"Tennessee Titans" rumor OR "Tennessee Titans" trade OR "Tennessee Titans" injury'
        ),
    },
    sitios_oficiales=["tennesseetitans.com"],
    # El techo lo fija el presupuesto del mensaje, no un 8 fijo: con enlaces
    # cortos caben ~3× titulares (#386).
    max_items=None,
    header_title="🏈 **Tennessee Titans — Noticias del día**",
    sources_line="Fuentes: Google News RSS (edición US) + tennesseetitans.com",
    prefilter_official=True,
    announce_overflow=True,
    dedupe_story=True,
    single_section=True,
    team_section_title="**🏈 TENNESSEE TITANS** ({count})",
    edition={"hl": "en-US", "gl": "US", "ceid": "US:en"},
    sitios_confiables=[
        "espn.com",
        "si.com",
        "cbssports.com",
        "foxsports.com",
        "nbcsports.com",
        "thetennessean.com",
    ],
    rumor_keywords=["rumor", "trade", "signing", "waive", "release", "injur"],
    # #386: en los feeds directos la previa y la cuota vienen del mismo medio;
    # medido sobre la jornada viva, esto se lleva 9 de 55 historias (16 %) y
    # ningún titular de noticia. En singular ("pick") hay falsos positivos
    # ("Fifth-Round Draft Pick"), así que el filtro va en plural.
    exclude_keywords=["odds", "betting", "bets", "spread", "parlay", "moneyline"],
    extra_section=ExtraSection(
        titulo="**🏈 NFL — La jornada** ({count})",
        query="site:nfl.com",
        categoria="liga",
        feeds=(
            (
                "FOX Sports",
                "https://api.foxsports.com/v1/rss"
                "?partnerKey=zBaFxRyGKCfxBagJG9b8pqLyndmvo7UU&tag=nfl",
            ),
            ("CBS Sports", "https://www.cbssports.com/rss/headlines/nfl/"),
        ),
    ),
)


def fetch_titans_official_impl(request: Request) -> list:
    """Listado del sitio oficial. Vacío declarado, no un fetch real.

    tennesseetitans.com es un sitio NFL (React): el listado no viene en el HTML
    servido, así que no hay nada que raspar. El dominio se declara en
    `sitios_oficiales` para que los enlaces oficiales que lleguen por Google
    News cuenten como confirmados. Cuando haya fetcher, se cambia solo esta
    función.
    """
    _ = request
    return []


def main() -> None:
    publish(
        lambda: build_report(
            CONFIG,
            history_path=history_path(CONFIG),
            fetch_official=lambda: fetch_titans_official_impl(retry_request),
        ),
        CONFIG.telegram_max_chars,
    )


if __name__ == "__main__":
    enter(main)
