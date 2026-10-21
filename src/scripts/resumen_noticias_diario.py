#!/usr/bin/env python3
"""Diario Global Hermes — fuentes multiregión, multi-ideología."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime

import defusedxml.ElementTree as ET  # noqa: N817

from hermes_common import (
    delivery,
    log_to_file_only,
    news_utils,
    repo_root,
    retry_request,
    setup_logging,
    smart_truncate,
    version_footer,
)
from scripts import polymarket_diario

log = logging.getLogger("hermes")

# Noticiero global (#149): 2-3 items por fuente (top por fecha, el orden
# de fetch_rss ya viene por fecha) con tope por subsección para no
# reventar el presupuesto Telegram.
ITEMS_POR_FUENTE = 3
# Cuota de subsección (#423): vive aquí, al lado del diario, porque no es el
# tope de Telegram — solo el diario la lee como techo por subsección.
MAX_CHARS_POR_SUBSECCION = 3000
# Items dropped per subsection, not per source (#469): enumerating every source grew the
# note to ~1000 u16 (a third of a message, measured 2026-10-10) while the cuts happen in the
# sections that are the report's point. Naming the subsections that lost the most says the
# same for 120 u16. The cap is a declaration, not an audit: the count is always stated.
MAX_SUBSECTIONS_IN_NOTE = 4

# Presupuesto de entrega (#278, medido 2026-09-23): el chunker de Hermes
# (gateway/platforms/base.py `truncate_message`) parte en el último '\n' del bloque, así que
# mientras NINGUNA LÍNEA pase del tope, un enlace no puede quedar partido. Eso permite volver a
# un reporte de varias tomas por sección: #212 lo había capado a 3200 (un mensaje) y ese techo es
# lo que forzó el `smart_truncate` que cortaba a mitad de la URL de Google News (208-244 chars).
# Medición: 1 mensaje = 3144 u16 con 6/10 enlaces reconocidos; el reporte rico de 2 mensajes
# (6119 u16) entrega 36/36. Presupuesto por MENSAJE, no por corrida.
# Fuente única (#423): los dos topes viven en `delivery` (REPORT_BUDGET y
# LINE_BUDGET); aquí solo se reexportan los nombres que ya usan los tests.
MAX_CHARS_REPORTE = delivery.REPORT_BUDGET
RESERVA_FUERA_DE_SECCIONES = 600
# Tope de una línea emitida: 4096 (Telegram) − marco del cron (~200) − indicador de chunk (10).
MAX_CHARS_LINEA = delivery.LINE_BUDGET
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
    "MAX_SUBSECTIONS_IN_NOTE",
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
    "nota_de_cuota",
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
    descartes: list | None = None,
) -> str:
    """Arma el bloque Markdown de una subsección, acotado a `cuota` caracteres.

    Reparte por rondas (#360): en la primera ronda entra el primer item de cada fuente, en
    el orden declarado, y las rondas siguientes agregan el resto. Antes se llenaba la
    primera fuente hasta la cuota y las demás quedaban fuera aunque tuvieran items frescos:
    con ~386 chars por subsección la primera se la comía entera (medido: 11 de 14
    subsecciones entregaban una sola fuente y ~1000 chars del presupuesto quedaban sin usar).

    Toma hasta ITEMS_POR_FUENTE por fuente (top por fecha), omite URLs ya vistas en
    el run (dedupe cross-sección) y recorta **por item completo**: ninguna línea se
    parte por la mitad.
    The bullet is emitted again when the emitted source changes and travels with
    that item, so it is never left orphaned.
    Partir una línea caía dentro de la URL de Google News (208-244 chars) y dejaba el
    enlace sin cerrar; Telegram lo entregaba como texto plano, con la URL a la vista
    (#278: 4 de 10 enlaces así).

    Un item que no cupo NO se marca como visto: puede salir en una sección siguiente
    si allí queda presupuesto. Tampoco condena a su fuente: la ronda siguiente prueba
    su item siguiente (mitad del defecto de #355).

    Args:
        sub_name: Nombre de la subsección (cabecera en itálicas).
        sources: Lista de (nombre, url).
        fetched: Lista de items por fuente, mismo orden que sources.
        seen_urls: Set de URLs ya emitidas; se actualiza in-place con lo que sí se emite.
        cuota: Inclusive UTF-16 length of the joined block, header included.

    Returns:
        str: Bloque Markdown, o "" si no cabe ni un item.
    """
    tope = MAX_CHARS_POR_SUBSECCION if cuota is None else cuota
    encabezado = f"*{sin_parentesis(sub_name)}*"
    lineas = [encabezado]
    candidatas: list = []
    for (source_name, _url), items in zip(sources, fetched):
        candidatos = []
        for title, link in (items or [])[:ITEMS_POR_FUENTE]:
            clean_link = escape_link(link)
            if clean_link in seen_urls:
                continue
            titulo = smart_truncate(sin_parentesis(clean_title(title)), limit=MAX_CHARS_TITULO)
            candidatos.append((f"  [{titulo}]({clean_link})", clean_link))
        if candidatos:
            candidatas.append(
                {
                    "nombre": source_name,
                    "bullet": f"• *{sin_parentesis(source_name)}*",
                    "items": candidatos,
                }
            )
    rondas = max((len(fuente["items"]) for fuente in candidatas), default=0)
    # Last source that actually emitted. A dropped item must not move it (#469).
    last_emitted = None
    for ronda in range(rondas):
        for fuente in candidatas:
            if ronda >= len(fuente["items"]):
                continue
            linea, url = fuente["items"][ronda]
            # Re-open the bullet when the emitted source changes. Consecutive
            # items of the same source share one. Bullet and item are one cost:
            # if the joined block does not fit, neither is emitted.
            propuesta = list(lineas)
            if last_emitted is not fuente:
                propuesta.append(fuente["bullet"])
            propuesta.append(linea)
            if delivery.utf16_len("\n".join(propuesta)) > tope:
                # No cabe este ítem. La ronda siguiente prueba el que sigue (#361);
                # el que se quedó fuera se cuenta para que el mensaje lo diga (#355).
                if descartes is not None:
                    descartes.append((sub_name, fuente["nombre"]))
                continue
            lineas = propuesta
            seen_urls.add(url)
            last_emitted = fuente
    return "\n".join(lineas) if len(lineas) > 1 else ""


def emitir_secciones(feeds, fetch, emit, presupuesto=MAX_CHARS_REPORTE, descartes=None):
    """Emit the sections that fit the delivery budget (#212, #278).

    Args:
        feeds: output of `load_feeds()`.
        fetch: `callable(sources) -> items`; `fetch_all_rss` in production.
        emit: `callable(str)`; `log.info` in production.
        presupuesto: maximum UTF-16 length of the emitted sections, including
            the blank line after each one. The masthead, footer and markets
            are outside this budget.

    Returns:
        list[str]: names of the omitted sections, in order of appearance. The budget is
            shared twice: a section's share is `max(fixed share, what is left //
            sections pending)` — the fixed share alone stranded whatever a section did
            not use (measured 2026-10-10: 968 u16) — and inside the section the share is
            redistributed among the subsections still pending. Without that split the
            first subsection ate the ceiling and the other framings never came out:
            that is how the 2026-09-23 report shipped with only `Mainstream / Wires`. A
            section whose content does not fit is omitted and its sources are not
            fetched.
    """
    seen_urls: set = set()
    usado = 0
    omitidas: list = []
    cuota = max(MIN_CHARS_SECCION, presupuesto // max(1, len(feeds)))
    for index, (section_name, subsections) in enumerate(feeds):
        restante = presupuesto - usado
        if restante < MIN_CHARS_SECCION:
            omitidas.append(section_name)
            continue
        # Dynamic share (#470): the fixed `presupuesto // sections` share strands whatever a
        # section does not use (measured 2026-10-10: GEOPOLITICA 162, AMERICAS 347, DEPORTES
        # 152 u16 free — 968 in total) and the next section cannot borrow it, so adding
        # sources rotates who shows instead of adding coverage. Same rule the subsection
        # split already applies below, one level up.
        section_share = max(cuota, restante // max(1, len(feeds) - index))
        encabezado = f"**{section_name}**"
        cap = min(section_share, restante)
        section_lines = [encabezado]
        for indice, (sub_name, sources) in enumerate(subsections):
            # Room left in the cap after the lines already chosen and the
            # blank line that follows the section. One unit of each share is
            # the newline that joins the next block.
            pending = len(subsections) - indice
            room = cap - (delivery.utf16_len("\n".join(section_lines)) + 1)
            cuota_sub = room // pending - 1
            if cuota_sub <= 0:
                continue
            fetched = fetch(sources)
            block = build_subsection_block(
                sub_name, sources, fetched, seen_urls, cuota=cuota_sub, descartes=descartes
            )
            if block:
                section_lines.append(block)
        if len(section_lines) == 1:
            continue
        texto = "\n".join(section_lines)
        emit(texto)
        emit("")
        usado += delivery.utf16_len(texto) + 1
        time.sleep(1)
    return omitidas


def _quota_note_line(total: int, subsections: int, named: list) -> str:
    """The quota note for a given list of named subsections.

    `subsections` is how many subsections lost items in the whole report, so the
    `+N más` marker counts what the line left out without depending on `candidates`
    (which is capped at `MAX_SUBSECTIONS_IN_NOTE`).
    """
    omitted = subsections - len(named)
    more = f" +{omitted} más" if omitted else ""
    tail = f" — {', '.join(named)}{more}" if named else ""
    noun = "subsección" if subsections == 1 else "subsecciones"
    unit = "ítem" if total == 1 else "ítems"
    return f"*fuera de cuota: {total} {unit} en {subsections} {noun}{tail}*"


def nota_de_cuota(descartes: list) -> str:
    """One line declaring what did not fit, counted per subsection (#469).

    It used to enumerate every source that lost an item (`Reuters 3, FT 3, AP 2`) and
    reached 982 u16 on the 2026-10-10 run — a third of a message describing cuts in the
    sections that are the report's point. Counting per subsection and naming the
    subsections that lost the most answers the same question (where was the cut, how
    much) for 120 u16: measured on the same run, 982 -> 120.

    Empty when nothing was dropped: the cron delivers stdout, so a line of its own would
    be a false declaration. Italics with `*`, never `_`. The count is the declaration and
    always goes out; names are added while they fit and dropped from the tail of the list
    when they do not, never splitting a line. The `for` over the candidates is the bound:
    no round can be added or removed without changing `MAX_SUBSECTIONS_IN_NOTE`.
    """
    if not descartes:
        return ""
    counts: dict[str, int] = {}
    for sub, _source in descartes:
        counts[sub] = counts.get(sub, 0) + 1
    total = sum(counts.values())
    candidates = [
        f"{sin_parentesis(sub)} {n}"
        for sub, n in sorted(counts.items(), key=lambda par: (-par[1], par[0]))
    ][:MAX_SUBSECTIONS_IN_NOTE]
    # The count-only line is the floor: it fits by construction and is never the one dropped.
    line = _quota_note_line(total, len(counts), [])
    for cut in range(1, len(candidates) + 1):
        candidate = _quota_note_line(total, len(counts), candidates[:cut])
        if delivery.utf16_len(candidate) > MAX_CHARS_LINEA:
            break
        line = candidate
    return line + "\n"


def nota_de_recorte(omitidas):
    """Aviso de recorte por presupuesto de entrega, para que el corte sea explícito."""
    return (
        f"\n✂️ *Por presupuesto de entrega de Telegram hoy quedaron fuera: "
        f"{', '.join(omitidas)}. Van mañana.*\n"
    )


def emit_polymarket_block():
    """Emit the Polymarket block, or leave the digest untouched when it fails.

    The block used to arrive as a child process whose stdout nobody read, so it
    never reached the delivery channel. The digest now fetches, renders and
    logs it itself (in-process since #422). A failure is a diagnostic for the
    audit log, never a line of the message (#457, #470): `log.info` and
    `log.warning` write to stdout, and for a `no_agent` job that stdout IS the
    delivered body, so a raw `Polymarket failed: …` reaches the reader between
    two sections.
    """
    try:
        cats, total_volume = polymarket_diario.fetch_classified_markets()
        block = polymarket_diario.build_block(cats, total_volume)
    except Exception as e:
        log_to_file_only(f"Polymarket failed: {e}")
        return
    fitted = delivery.prepare([block])
    text = fitted[0].text if fitted else ""
    for line in text.splitlines():
        log.info(line)


# Public-domain sayings. The cron does not fetch them. The index is the day
# of the year, so 1 January is always the first line and the list repeats
# every fourteen days.
DAILY_PHRASES = (
    "La verdad es hija del tiempo.",
    "Del dicho al hecho hay mucho trecho.",
    "No hay mal que por bien no venga.",
    "El que mucho abarca poco aprieta.",
    "Más vale tarde que nunca.",
    "Quien siembra vientos recoge tempestades.",
    "El hábito no hace al monje.",
    "Agua pasada no mueve molino.",
    "No por mucho madrugar amanece más temprano.",
    "A caballo regalado no se le mira el diente.",
    "Cada quien habla de la feria según le va en ella.",
    "El que no oye consejo no llega a viejo.",
    "Ojos que no ven, corazón que no siente.",
    "Más vale pájaro en mano que ciento volando.",
)


def phrase_line(day: date) -> str:
    """One italic saying for this day of the year.

    Italics use `*`, never `_`: Hermes delivers underscores as visible
    characters (ADR 0005). The line stays out of the section budget.
    """
    index = (day - day.replace(month=1, day=1)).days % len(DAILY_PHRASES)
    return f"*{DAILY_PHRASES[index]}* — refrán"


def masthead(when: datetime) -> str:
    """Title, one date, and the day's saying. One message, before the sections."""
    return (
        "🪨 **DIARIO GLOBAL HERMES** 🪨\n"
        f"*Fecha: {when.strftime('%Y-%m-%d %H:%M')}*\n"
        f"{phrase_line(when.date())}\n"
    )


def main():
    setup_logging()
    log.info(masthead(datetime.now()))
    time.sleep(0.5)

    feeds = load_feeds()
    # Ojo: aquí NO se sanea la línea completa. `sin_parentesis` sobre el texto
    # emitido se come los paréntesis del enlace `[titulo](url)` y lo rompe: el
    # saneo vive en titulares, nombres de fuente y subsección (#212).
    descartes: list = []
    omitidas = emitir_secciones(feeds, fetch_all_rss, log.info, descartes=descartes)
    if omitidas:
        log.info(nota_de_recorte(omitidas))
        time.sleep(1)
    nota = nota_de_cuota(descartes)
    if nota:
        log.info(nota)
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

    # Polymarket predictions (in-process since #422: the child stdout
    # went nowhere, so the block never reached the delivery channel)
    emit_polymarket_block()

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
