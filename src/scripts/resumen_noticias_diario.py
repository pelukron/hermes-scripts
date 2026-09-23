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

from hermes_common import (
    news_utils,
    repo_root,
    retry_request,
    setup_logging,
    smart_truncate,
    version_footer,
)

log = logging.getLogger("hermes")

# Noticiero global (#149): 2-3 items por fuente (top por fecha, el orden
# de fetch_rss ya viene por fecha) con tope por subsección para no
# reventar el presupuesto Telegram.
ITEMS_POR_FUENTE = 3
MAX_CHARS_POR_SUBSECCION = news_utils.TELEGRAM_MAX_CHARS

# Presupuesto de entrega (#278, medido 2026-09-23): el chunker de Hermes
# (gateway/platforms/base.py `truncate_message`) parte en el último '\n' del bloque, así que
# mientras NINGUNA LÍNEA pase del tope, un enlace no puede quedar partido. Eso permite volver a
# un reporte de varias tomas por sección: #212 lo había capado a 3200 (un mensaje) y ese techo es
# lo que forzó el `smart_truncate` que cortaba a mitad de la URL de Google News (208-244 chars).
# Medición: 1 mensaje = 3144 u16 con 6/10 enlaces reconocidos; el reporte rico de 2 mensajes
# (6119 u16) entrega 36/36. Presupuesto por MENSAJE, no por corrida.
MAX_CHARS_REPORTE = 7100
RESERVA_FUERA_DE_SECCIONES = 600
# Tope de una línea emitida: 4096 (Telegram) − marco del cron (~200) − indicador de chunk (10).
MAX_CHARS_LINEA = 3800
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
    "MAX_CHARS_LINEA",
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
    cuota: int | None = None,
) -> str:
    """Arma el bloque Markdown de una subsección, acotado a `cuota` caracteres.

    Toma hasta ITEMS_POR_FUENTE por fuente (top por fecha), omite URLs ya vistas en
    el run (dedupe cross-sección) y recorta **por item completo**: el bullet de una
    fuente es indivisible de su primer item y ninguna línea se parte por la mitad.
    Partir una línea caía dentro de la URL de Google News (208-244 chars) y dejaba el
    enlace sin cerrar; Telegram lo entregaba como texto plano, con la URL a la vista
    (#278: 4 de 10 enlaces así).

    Un item que no cupo NO se marca como visto: puede salir en una sección siguiente
    si allí queda presupuesto.

    Args:
        sub_name: Nombre de la subsección (cabecera en itálicas).
        sources: Lista de (nombre, url).
        fetched: Lista de items por fuente, mismo orden que sources.
        seen_urls: Set de URLs ya emitidas; se actualiza in-place con lo que sí se emite.
        cuota: Presupuesto de caracteres del bloque, cabecera incluida.

    Returns:
        str: Bloque Markdown, o "" si no cabe ni un item.
    """
    tope = MAX_CHARS_POR_SUBSECCION if cuota is None else cuota
    encabezado = f"*{sin_parentesis(sub_name)}*"
    lineas = [encabezado]
    usado = len(encabezado) + 1
    for (source_name, _url), items in zip(sources, fetched):
        bullet = f"• *{sin_parentesis(source_name)}*"
        candidatos = []
        for title, link in (items or [])[:ITEMS_POR_FUENTE]:
            clean_link = escape_link(link)
            if clean_link in seen_urls:
                continue
            titulo = smart_truncate(sin_parentesis(clean_title(title)), limit=MAX_CHARS_TITULO)
            candidatos.append((f"  [{titulo}]({clean_link})", clean_link))
        if not candidatos:
            continue
        # El bullet viaja con su primer item; los siguientes entran de uno en uno.
        gastado = usado + len(bullet) + 1 + len(candidatos[0][0]) + 1
        if gastado > tope:
            continue
        emitidos = [candidatos[0]]
        for candidato in candidatos[1:]:
            if gastado + len(candidato[0]) + 1 > tope:
                break
            emitidos.append(candidato)
            gastado += len(candidato[0]) + 1
        lineas.append(bullet)
        for linea, url in emitidos:
            lineas.append(linea)
            seen_urls.add(url)
        usado = gastado
    return "\n".join(lineas) if len(lineas) > 1 else ""


def emitir_secciones(feeds, fetch, emit, presupuesto=MAX_CHARS_REPORTE):
    """Emite las secciones que caben en el presupuesto de entrega (#212, #278).

    Args:
        feeds: salida de `load_feeds()`.
        fetch: `callable(sources) -> items`; en producción `fetch_all_rss`.
        emit: `callable(str)`; en producción `log.info`.
        presupuesto: máximo de caracteres de secciones a emitir (sin contar
            encabezado, pie ni mercados).

    Returns:
        list[str]: nombres de las secciones omitidas, en orden de aparición.
            El presupuesto se reparte en una cuota por sección y, dentro de la sección,
            en una cuota por subsección que se redistribuye entre las que faltan: sin ese
            reparto la primera subsección se come el techo y los demás encuadres no salen
            —así se entregaba el 2026-09-23, con solo `Mainstream / Wires` publicado—.
            Una sección cuyo contenido no cabe se omite y sus fuentes no se piden.
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
        encabezado = f"**{section_name}**"
        disponible = min(cuota, restante) - len(encabezado) - 1
        section_lines = [encabezado]
        for indice, (sub_name, sources) in enumerate(subsections):
            cuota_sub = disponible // (len(subsections) - indice)
            if cuota_sub <= 0:
                continue
            fetched = fetch(sources)
            block = build_subsection_block(sub_name, sources, fetched, seen_urls, cuota=cuota_sub)
            if block:
                section_lines.append(block)
                disponible -= len(block) + 1
        if len(section_lines) == 1:
            continue
        texto = "\n".join(section_lines)
        emit(texto)
        emit("")
        usado += len(texto) + 1
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
    log.info(
        f"🪨 **DIARIO GLOBAL HERMES** 🪨\n*Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
    )
    time.sleep(0.5)

    feeds = load_feeds()
    # Ojo: aquí NO se sanea la línea completa. `sin_parentesis` sobre el texto
    # emitido se come los paréntesis del enlace `[titulo](url)` y lo rompe: el
    # saneo vive en titulares, nombres de fuente y subsección (#212).
    omitidas = emitir_secciones(feeds, fetch_all_rss, log.info)
    if omitidas:
        log.info(nota_de_recorte(omitidas))
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
        footer_line += "\n"
        footer_line += version_footer() + "\n"
        log.info(footer_line)
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
        log.info("**💰 MERCADOS**\n")
        for sym, price, change, emoji in crypto:
            log.info(f"• {emoji} {sym}: ${price:,.2f} {change:+.2f}%")
        for label, rate, note in curr:
            log.info(f"• {label}: ${rate:,.2f} {note}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
