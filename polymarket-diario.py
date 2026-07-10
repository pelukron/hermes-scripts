#!/usr/bin/env python3
"""Polymarket diario — mercados activos trending para noticias.

Output: Markdown. $0 tokens. API pública sin auth.
"""

import json
import random
import time

import requests

API = "https://gamma-api.polymarket.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def retry_request(url, timeout=15, max_attempts=3):
    """Fetch URL with exponential backoff + jitter. Retries on transient failures only.

    Args:
        url (str): URL a consultar.
        timeout (int): Timeout en segundos por intento.
        max_attempts (int): Número máximo de intentos.

    Returns:
        requests.Response: Respuesta HTTP exitosa.

    Raises:
        requests.ConnectionError: Si se agotan reintentos por error de conexión.
        requests.Timeout: Si se agotan reintentos por timeout.
        requests.HTTPError: Si el status code no es 2xx y no es reintentable.

    """
    retry_status = {429, 500, 502, 503, 504}
    for attempt in range(max_attempts):
        try:
            r = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": UA, "Accept": "application/json"},
            )
            if r.status_code in retry_status and attempt < max_attempts - 1:
                wait = (2**attempt) + random.uniform(0, 0.5)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except (requests.ConnectionError, requests.Timeout, ConnectionError, TimeoutError):
            if attempt < max_attempts - 1:
                wait = (2**attempt) + random.uniform(0, 0.5)
                time.sleep(wait)
            else:
                raise
        except requests.HTTPError:
            raise
    return None


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


def main():
    """Punto de entrada: consulta Polymarket, clasifica mercados, imprime reporte Markdown.

    Secciones: Geopolítica, Elecciones 2028, Deportes.
    Filtra mercados con probabilidad entre 5% y 95%.

    """
    print()
    print("█ 🔮 MERCADOS DE PREDICCIÓN █")
    print()

    try:
        events = fetch(f"{API}/events?closed=false&order=volume&ascending=false&limit=25")
    except Exception as e:
        print(f"  ⚠️ Sin datos: {e}")
        return

    cats = {"geopolitica": [], "elecciones": [], "deportes": []}

    for ev in events:
        if ev.get("closed"):
            continue
        cat = classify(ev.get("title"), ev.get("tags"))
        if cat and cat in cats and len(cats[cat]) < 4:
            leader, prob = best_market(ev.get("markets"))
            if leader and prob and 5.0 <= prob <= 95.0:
                cats[cat].append(
                    {
                        "title": (ev.get("title") or "?")[:50],
                        "question": (leader.get("question") or "?")[:55],
                        "prob": prob,
                        "vol": fmt_vol(ev.get("volume", 0)),
                    }
                )

    # Geopolítica
    if cats["geopolitica"]:
        print("🌍 GEOPOLÍTICA")
        for item in cats["geopolitica"]:
            print(f"- **{item['title']}**")
            print(f"  🔮 {item['question']} → **{item['prob']}%**")
            print(f"  📊 Vol: {item['vol']}")
        print()

    # Elecciones
    if cats["elecciones"]:
        print("🇺🇸 ELECCIONES 2028")
        print("| Candidato | Prob | Vol |")
        print("|-----------|------|-----|")
        for item in cats["elecciones"]:
            print(f"| {item['question']} | {item['prob']}% | {item['vol']} |")
        print()

    # Deportes
    if cats["deportes"]:
        print("⚽ DEPORTES")
        print("| Evento | Top | Prob | Vol |")
        print("|--------|-----|------|-----|")
        for item in cats["deportes"]:
            print(f"| {item['title']} | {item['question']} | {item['prob']}% | {item['vol']} |")
        print()

    total = sum(float(ev.get("volume", 0) or 0) for ev in events[:10])
    print(f"_Volumen top 10: {fmt_vol(total)} • Fuente: Polymarket_")


if __name__ == "__main__":
    main()
