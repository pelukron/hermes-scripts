#!/usr/bin/env python3
"""Polymarket diario — mercados activos trending para noticias.

Output: Markdown. $0 tokens. API pública sin auth.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from hermes_common import retry_request, setup_logging, version_footer

log = logging.getLogger("hermes")


@dataclass
class MarketEntry:
    """Mercado clasificado para el reporte (issue #73)."""

    title: str = "?"
    question: str = "?"
    prob: Optional[float] = None
    vol: str = "—"


API = "https://gamma-api.polymarket.com"

TAGS_GEO = [
    "politics",
    "geopolitics",
    "election",
    "war",
    "conflict",
    "middle-east",
    "latin-america",
    "brazil",
    "venezuela",
    "france",
    "china",
    "russia",
    "nato",
    "iran",
    "netanyahu",
    "ukraine",
    "germany",
    "africa",
    "ethiopia",
    "europe",
]
TAGS_DEP = [
    "sports",
    "soccer",
    "football",
    "world-cup",
    "world cup",
    "fifa",
    "f1",
    "liga-mx",
    "champions",
    "nba",
    "nfl",
    "mlb",
]
TAGS_ELE = [
    "democratic",
    "republican",
    "nominee",
    "election 2028",
    "presidential election",
    "presidential nominee",
]


def fetch(url):
    """Obtiene JSON desde API Polymarket con reintentos ante fallos transitorios.

    Args:
        url (str): URL completa del endpoint.

    Returns:
        dict: Respuesta JSON parseada.

    Raises:
        requests.HTTPError: Si la API responde con error no recuperable.
        requests.ConnectionError: Si se agotan reintentos de conexión.

    """
    r = retry_request(url, timeout=15)
    return r.json()


def pct(prices_json):
    """Convierte outcomePrices de Polymarket a porcentaje.

    Args:
        prices_json (str | list | None): JSON con array de precios.

    Returns:
        Optional[float]: Porcentaje (0-100), o None si no hay datos.

    """
    if not prices_json:
        return None
    try:
        p = json.loads(prices_json) if isinstance(prices_json, str) else prices_json
        return round(float(p[0]) * 100, 1) if p else None
    except Exception:
        return None


def fmt_vol(v):
    """Formatea volumen a formato legible (B/M/K).

    Args:
        v (float | str | None): Volumen numérico.

    Returns:
        str: String formateado (ej. \"$2.5M\", \"$500K\", \"—\").

    """
    try:
        v = float(v) if v else 0
        if v >= 1e9:
            return f"${v / 1e9:.2f}B"
        if v >= 1e6:
            return f"${v / 1e6:.1f}M"
        if v >= 1e3:
            return f"${v / 1e3:.0f}K"
        return f"${v:.0f}"
    except Exception:
        return "—"


def classify(title, tags_raw):
    """Clasifica mercado en categoría: geopolitica, elecciones, deportes.

    Busca keywords en título + tags contra TAGS_GEO, TAGS_DEP, TAGS_ELE.

    Args:
        title (str | None): Título del evento.
        tags_raw (list | None): Lista de tags del evento.

    Returns:
        Optional[str]: Categoría asignada, o None si no clasifica.

    """
    text = (title or "").lower()
    for t in tags_raw or []:
        if isinstance(t, dict):
            text += " " + (t.get("label", "") or "").lower()
            text += " " + (t.get("slug", "") or "").lower()
    for kw in TAGS_ELE:
        if kw in text:
            return "elecciones"
    for kw in TAGS_DEP:
        if kw in text:
            return "deportes"
    for kw in TAGS_GEO:
        if kw in text:
            return "geopolitica"
    return None


def best_market(markets):
    """Find market with highest probability from active markets."""
    best, best_p = None, -1
    for m in markets or []:
        if m.get("closed"):
            continue
        prob = pct(m.get("outcomePrices"))
        if prob is not None and prob > best_p:
            best_p, best = prob, m
    return best, best_p


def fetch_classified_markets():
    """Fetch events and sort them into the report categories.

    Returns:
        tuple: (cats, total_volume) with the classified MarketEntry lists
            (up to 4 per category, probability between 5% and 95%) and the
            top-10 volume used by the footer.

    Raises:
        requests.HTTPError: Si la API responde con error no recuperable.
        requests.ConnectionError: Si se agotan reintentos de conexión.

    """
    events = fetch(f"{API}/events?closed=false&order=volume&ascending=false&limit=25")
    cats = {"geopolitica": [], "elecciones": [], "deportes": []}
    for ev in events:
        if ev.get("closed"):
            continue
        cat = classify(ev.get("title"), ev.get("tags"))
        if cat and cat in cats and len(cats[cat]) < 4:
            leader, prob = best_market(ev.get("markets"))
            if leader and prob and 5.0 <= prob <= 95.0:
                cats[cat].append(
                    MarketEntry(
                        title=(ev.get("title") or "?")[:50],
                        question=(leader.get("question") or "?")[:55],
                        prob=prob,
                        vol=fmt_vol(ev.get("volume", 0)),
                    )
                )
    total = sum(float(ev.get("volume", 0) or 0) for ev in events[:10])
    return cats, total


def build_block(cats, total_volume):
    """Render the already classified payload as the report markdown.

    Pure: no fetch, no logging. The caller decides the sink (standalone
    ``main`` logs it, the daily digest passes it to its own logger).

    Args:
        cats (dict): Clasified MarketEntry lists by category.
        total_volume (float): Top-10 volume for the footer.

    Returns:
        str: Markdown block, one section per non-empty category.

    """
    lines = [
        "",
        "█ 🔮 MERCADOS DE PREDICCIÓN █",
        version_footer(),
        "",
    ]
    if cats["geopolitica"]:
        lines.append("🌍 GEOPOLÍTICA")
        for item in cats["geopolitica"]:
            lines.append(f"- **{item.title}**")
            lines.append(f"  🔮 {item.question} → **{item.prob}%**")
            lines.append(f"  📊 Vol: {item.vol}")
        lines.append("")
    if cats["elecciones"]:
        lines.append("🇺🇸 ELECCIONES 2028")
        lines.append("| Candidato | Prob | Vol |")
        lines.append("|-----------|------|-----|")
        for item in cats["elecciones"]:
            lines.append(f"| {item.question} | {item.prob}% | {item.vol} |")
        lines.append("")
    if cats["deportes"]:
        lines.append("⚽ DEPORTES")
        lines.append("| Evento | Top | Prob | Vol |")
        lines.append("|--------|-----|------|-----|")
        for item in cats["deportes"]:
            lines.append(f"| {item.title} | {item.question} | {item.prob}% | {item.vol} |")
        lines.append("")
    lines.append(f"*Volumen top 10: {fmt_vol(total_volume)} • Fuente: Polymarket*")
    return "\n".join(lines)


def main():
    """Punto de entrada: consulta Polymarket, clasifica mercados, imprime reporte Markdown.

    Secciones: Geopolítica, Elecciones 2028, Deportes.
    Filtra mercados con probabilidad entre 5% y 95%.

    """
    setup_logging()
    try:
        cats, total_volume = fetch_classified_markets()
    except Exception as e:
        log.warning(f"  ⚠️ Sin datos: {e}")
        return
    for line in build_block(cats, total_volume).splitlines():
        log.info(line)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
