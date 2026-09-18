#!/usr/bin/env python3
"""Diario Global Hermes — fuentes multiregión, multi-ideología."""

import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

import defusedxml.ElementTree as ET  # noqa: N817

from hermes_common import news_utils, repo_root, retry_request, setup_logging, smart_truncate

log = logging.getLogger("hermes")

# Noticiero global (#149): 2-3 items por fuente (top por fecha, el orden
# de fetch_rss ya viene por fecha) con tope por subsección para no
# reventar el presupuesto Telegram.
ITEMS_POR_FUENTE = 3
MAX_CHARS_POR_SUBSECCION = news_utils.TELEGRAM_MAX_CHARS

# Presupuesto de entrega (#212, medido 2026-09-18): el sender de Telegram corta a
# 4096 unidades UTF-16 por mensaje. Con 2 chunks el corte parte un enlace por la
# mitad y Telegram RECHAZA el markdown de ese chunk: se entrega como texto plano y
# quedan a la vista las URLs de Google News (~200 chars). Con 1 chunk el render es
# limpio, así que el techo es un solo mensaje. Títulos y paréntesis van acotados.
MAX_CHARS_REPORTE = 3200
RESERVA_FUERA_DE_SECCIONES = 600
# Una sección por debajo de esto no vale el viaje: encabezado + nombre de fuente
# + un item con su link. Si lo que queda del presupuesto no llega, la sección se
# omite SIN pedir sus fuentes (ahorra red en la cola del reporte).
MIN_CHARS_SECCION = 250
# Titular máximo por item (#212): los feeds sirven titulares de 100-150 chars y
# el reporte muestra la URL al lado, así que el mensaje se vuelve ilegible.
MAX_CHARS_TITULO = 80

# Helpers compartidos en src/hermes_common/news_utils.py (issue #70).
clean_title = news_utils.clean_title

# Re-exports de compatibilidad (tests y otros importadores usan mod.<helper>).
__all__ = [
    "ITEMS_POR_FUENTE",
    "MAX_CHARS_POR_SUBSECCION",
    "MAX_CHARS_REPORTE",
    "MAX_CHARS_TITULO",
    "RESERVA_FUERA_DE_SECCIONES",
    "build_subsection_block",
    "clean_title",
    "emitir_secciones",
    "escape_link",
    "fetch_all_rss",
    "fetch_crypto",
    "fetch_currencies",
    "fetch_rss",
    "load_feeds",
    "nota_de_recorte",
]


def escape_link(link):
    """Normaliza URLs de Google News: quita tracking params y protege caracteres especiales."""
    return news_utils.clean_url(link, escape_parens=True)


# FEEDS hardcodeado eliminado (#70): la fuente viva es config/feeds.json vía load_feeds().


# ── Dataclasses ──
@dataclass
class FeedItem:
    title: str
    link: str


@dataclass
class FeedStats:
    ok: int = 0
    fail: int = 0
    failed: list = field(default_factory=list)

    def track_ok(self):
        self.ok += 1

    def track_fail(self, name: str):
        self.fail += 1
        self.failed.append(name)


_stats = FeedStats()


def load_feeds(path="config/feeds.json"):
    """Carga las fuentes desde la raíz del repo (no desde src/scripts/, #207)."""
    full_path = repo_root() / path
    with open(full_path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        (
            s["name"],
            [
                (
                    sub["name"],
                    [(src["name"], src["url"]) for src in sub["sources"]],
                )
                for sub in s["subsections"]
            ],
        )
        for s in data["sections"]
    ]


# Namespaces for RDF feeds (DW, etc.)
RDF_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss": "http://purl.org/rss/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def fetch_rss(url, source_name=""):
    try:
        r = retry_request(url)
        if r is None:
            _stats.track_fail(source_name)
            return []
        root = ET.fromstring(r.content)
        items = []

        # Try standard RSS first, fall back to RDF
        item_elements = root.findall(".//item")
        if not item_elements:
            item_elements = root.findall(".//rss:item", RDF_NS)

        for item in item_elements[:4]:
            # Try standard title, then RDF title
            title = item.find("title")
            if title is None:
                title = item.find("rss:title", RDF_NS)
            if title is None or not title.text:
                continue
            title_text = title.text.strip()
            # Skip "Google News" boilerplate titles
            if title_text.startswith('"') and " when:" in title_text:
                continue

            # Try standard link, then RDF link
            link_node = item.find("link")
            if link_node is None:
                link_node = item.find("rss:link", RDF_NS)
            link = ""
            if link_node is not None:
                link = link_node.text if link_node.text else link_node.attrib.get("href", "")
            if title_text and link:
                items.append((title_text, link.strip()))
        _stats.track_ok()
        return items
    except Exception:
        _stats.track_fail(source_name)
        return []


def fetch_all_rss(sources, max_workers=4, stagger=0.2):
    """Fetch concurrente de feeds preservando el orden de entrada.

    Args:
        sources: Lista de (nombre, url).
        max_workers: Hilos en paralelo.
        stagger: Pausa entre envíos (rate-limiting respetuoso con los hosts).

    Returns:
        list: Una lista de items por fuente, en el mismo orden de entrada.
    """
    results: list = [[] for _ in sources]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for source_name, url in sources:
            futures.append(pool.submit(fetch_rss, url, source_name))
            if stagger > 0:
                time.sleep(stagger)
        for idx, future in enumerate(futures):
            try:
                results[idx] = future.result() or []
            except Exception:
                results[idx] = []
    return results


def fetch_crypto():
    try:
        ids = "bitcoin,ethereum,solana,binancecoin"
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
        r = retry_request(url)
        if r is None:
            return []
        data = r.json()
        mapping = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "binancecoin": "BNB"}
        result = []
        for id_key, display in mapping.items():
            if id_key in data:
                price = data[id_key].get("usd", 0)
                change = data[id_key].get("usd_24h_change", 0)
                emoji = "🟢" if change >= 0 else "🔴"
                result.append((display, price, change, emoji))
        return result
    except Exception:
        return []


def fetch_currencies():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        r = retry_request(url)
        if r is None:
            return []
        base = r.json().get("rates", {})
        mxn = base.get("MXN", 0)
        return [("💵 USD/MXN", mxn, "Base USD")] if mxn else []
    except Exception:
        return []


def sin_parentesis(texto):
    """Quita paréntesis de un texto del feed (#212).

    MarkdownV2 los exige escapados y el sender de Hermes no los escapa en el
    texto del link: el mensaje entero cae a texto plano y las URLs de Google
    News (~200 chars) quedan a la vista al lado de cada titular.
    """
    return texto.replace("(", "").replace(")", "")


def build_subsection_block(
    sub_name: str,
    sources: list,
    fetched: list,
    seen_urls: set,
) -> str:
    """Arma el bloque Markdown de una subsección.

    Toma hasta ITEMS_POR_FUENTE por fuente (top por fecha), omite URLs
    ya vistas en el run (dedupe cross-sección) y acota el bloque a
    MAX_CHARS_POR_SUBSECCION vía smart_truncate.

    Args:
        sub_name: Nombre de la subsección (cabecera en itálicas).
        sources: Lista de (nombre, url).
        fetched: Lista de items por fuente, mismo orden que sources.
        seen_urls: Set de URLs ya emitidas; se actualiza in-place.

    Returns:
        str: Bloque Markdown o "" si no hay contenido nuevo.
    """
    sub_lines = [f"_{sub_name}_"]
    has_content = False
    for (source_name, _url), items in zip(sources, fetched):
        new_lines = []
        for title, link in (items or [])[:ITEMS_POR_FUENTE]:
            clean_link = escape_link(link)
            if clean_link in seen_urls:
                continue
            seen_urls.add(clean_link)
            titulo = smart_truncate(sin_parentesis(clean_title(title)), limit=MAX_CHARS_TITULO)
            new_lines.append(f"  [{titulo}]({clean_link})")
        if new_lines:
            has_content = True
            sub_lines.append(f"• *{sin_parentesis(source_name)}*")
            sub_lines.extend(new_lines)
    if not has_content:
        return ""
    return smart_truncate("\n".join(sub_lines), limit=MAX_CHARS_POR_SUBSECCION)


def emitir_secciones(feeds, fetch, emit, presupuesto=MAX_CHARS_REPORTE):
    """Emite las secciones que caben en el presupuesto de entrega (#212).

    Args:
        feeds: salida de `load_feeds()`.
        fetch: `callable(sources) -> items`; en producción `fetch_all_rss`.
        emit: `callable(str)`; en producción `log.info`.
        presupuesto: máximo de caracteres de secciones a emitir (sin contar
            encabezado, pie ni mercados).

    Returns:
        list[str]: nombres de las secciones omitidas, en orden de aparición.
            El presupuesto se reparte en una cuota por sección (no es
            primero-llega-se-lo-lleva: la primera sección no puede dejar sin
            espacio a las demás). Una sección cuyo texto se trunca a la cuota
            sí se emite; solo se omite si lo que queda del presupuesto no llega
            para el mínimo, y en ese caso no se piden sus fuentes (ahorra red).
    """
    seen_urls: set = set()
    usado = 0
    omitidas: list = []
    cuota = max(MIN_CHARS_SECCION, presupuesto // max(1, len(feeds)))
    for section_name, subsections in feeds:
        restante = presupuesto - usado
        if restante < MIN_CHARS_SECCION:
            omitidas.append(section_name)
            continue
        section_lines = [f"**{section_name}**"]
        section_has_content = False
        for sub_name, sources in subsections:
            fetched = fetch(sources)
            block = build_subsection_block(sub_name, sources, fetched, seen_urls)
            if block:
                section_lines.append(block)
                section_has_content = True
        if not section_has_content:
            continue
        texto = smart_truncate("\n".join(section_lines), limit=min(cuota, restante))
        emit(texto)
        emit("")
        usado += len(texto)
        time.sleep(1)
    return omitidas


def nota_de_recorte(omitidas):
    """Aviso de recorte por presupuesto de entrega, para que el corte sea explícito."""
    return (
        f"\n✂️ _Por presupuesto de entrega de Telegram hoy quedaron fuera: "
        f"{', '.join(omitidas)}. Van mañana._\n"
    )


def main():
    setup_logging()

    def emitir(texto):
        """Todo lo que sale al canal pasa por aquí: sin paréntesis que tiren el
        MarkdownV2 a texto plano, con las URLs gigantes a la vista (#212)."""
        log.info(sin_parentesis(texto))

    emitir(
        f"🪨 **DIARIO GLOBAL HERMES** 🪨\n_Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"
    )
    time.sleep(0.5)

    feeds = load_feeds()
    omitidas = emitir_secciones(feeds, fetch_all_rss, emitir)
    if omitidas:
        emitir(nota_de_recorte(omitidas))
        time.sleep(1)

    # Footer stats
    total_sources = _stats.ok + _stats.fail
    if total_sources > 0:
        status = "✅" if _stats.fail == 0 else "⚠️"
        footer_line = f"\n📊 {status} Fuentes: {_stats.ok}/{total_sources} OK"
        if _stats.fail > 0:
            failed_list = ", ".join(_stats.failed[:5])
            if _stats.fail > 5:
                failed_list += f" +{_stats.fail - 5} más"
            footer_line += f" {_stats.fail} fallos: {failed_list}"
        footer_line += "_\n"
        emitir(footer_line)
        time.sleep(1)

    # Polymarket predictions (entrypoint instalado por #71)
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.polymarket_diario"],
            timeout=25,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        log.warning("Polymarket subprocess failed: %s", e)

    # Markets
    crypto = fetch_crypto()
    curr = fetch_currencies()
    if crypto or curr:
        emitir("**💰 MERCADOS**\n")
        for sym, price, change, emoji in crypto:
            emitir(f"• {emoji} {sym}: ${price:,.2f} {change:+.2f}%")
        for label, rate, note in curr:
            emitir(f"• {label}: ${rate:,.2f} {note}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
