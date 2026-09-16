#!/usr/bin/env python3
"""
resumen-tigres-diario.py
Recopila noticias de Tigres UANL para un resumen diario en Telegram.
Fuentes:
  1) Google News RSS México (palabras clave de Tigres).
  2) Sitio oficial tigres.com.mx (noticias recientes).

Divide resultados en:
  - Noticias confirmadas (medios establecidos y sitio oficial).
  - Rumores/filtraciones (con disclaimer de no confirmación).

Uso:
  resumen-tigres-diario
"""

import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import hermes_common
from hermes_common import filter_by_max_age, news_utils, parse_published, retry_request

# Cron job uses the Hermes venv by default; ensure deps are installed if missing.
try:
    import feedparser  # noqa: F401 — re-exportado en __all__ (target de mocks en tests)
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    import shutil
    import subprocess

    uv = os.environ.get("UV") or shutil.which("uv") or os.path.expanduser("~/.hermes/bin/uv")
    if not os.path.isfile(uv):
        uv = "uv"  # fallback to system PATH
    try:
        subprocess.check_call(
            [
                uv,
                "pip",
                "install",
                "--python",
                sys.executable,
                "feedparser",
                "requests",
                "beautifulsoup4",
                "lxml",
            ]
        )
    except subprocess.CalledProcessError as e:
        logging.warning("Failed to install runtime deps: %s", e)
        raise
    import feedparser  # noqa: F401 — re-exportado en __all__ (target de mocks en tests)
    from bs4 import BeautifulSoup

# Telegram: límite de un mensaje = 4096 caracteres; dejamos margen para cabeceras de formato.
TELEGRAM_MAX_CHARS = 3000

# Máximo de items que se muestran por sección (confirmadas / rumores)
MAX_ITEMS_POR_SECCION = 8

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
TIMEOUT = 20

# Palabras clave para cada categoría en Google News RSS México.
# Sintaxis verificada (feed válido HTTP 200 pero 0 entries si se viola):
# - La query debe ABRIR con una frase entre comillas dobles; solo términos
#   sueltos (sin ninguna frase citada) dan 0 resultados.
# - `OR` entre frases citadas SÍ funciona; también una frase citada seguida
#   de términos sueltos (ej: "Tigres UANL" fichaje).
# - `AND` explícito y paréntesis `(` `)` rompen el feed (0 entries) → prohibidos.
QUERIES = {
    "confirmadas": '"Tigres UANL" OR "Club Tigres" OR "Tigres de Monterrey"',
    "rumores": ('"Tigres UANL" fichaje OR "Tigres UANL" refuerzo OR "Tigres UANL" lesion'),
}

# Dominios considerados medios establecidos / fuentes oficiales
SITIOS_OFICIALES = ["tigres.com.mx"]
SITIOS_CONFIABLES = [
    "milenio.com",
    "elsoldemonterrey.com.mx",
    "marca.com",
    "espn.com.mx",
    "mediotiempo.com",
    "record.com.mx",
    "tudn.com",
    "foxdeportes.com",
    "tvazteca.com",
    "lineadirectaportal.com",
    "eluniversal.com.mx",
    "reforma.com",
    "jornada.com.mx",
    "elporvenir.com.mx",
    "rg.sport",
    "onefootball.com",
    "as.com",
    "espndeportes.espn.com",
    "deportes.televisa.com",
    "aztecadeportes.com",
    "sopitas.com",
    "cancunmio.com",
]

# Patrones que indican rumor / filtración / no confirmado en el título
RUMOR_KEYWORDS = [
    "rumor",
    "filtr",
    "filtran",
    "apunta",
    "podría",
    "interesado",
    "interesa",
    "oferta",
    "negocia",
    "negociaciones",
    "cerca de",
    "a un paso",
    "sondea",
    "sondeo",
    "pretende",
    "busca",
    "quiere",
    "vinculado",
    "en la mira",
    "mercado de pases",
    "fichaje",
    "refuerzo",
    "baja",
    "lesionado",
]


# ---------------------------------------------------------------------------
# Helpers compartidos en src/hermes_common/news_utils.py (issue #70).
# Aquí solo quedan wrappers finos ligados a las constantes de Tigres.
# Los alias directos mantienen compatibilidad con mod.<helper>.
# ---------------------------------------------------------------------------
build_google_news_url = news_utils.build_google_news_url
canonical_title = news_utils.canonical_title
clean_title = news_utils.clean_title
clean_url = news_utils.clean_url
dedupe = news_utils.dedupe
dedupe_by_title = news_utils.dedupe_by_title
domain_of = news_utils.domain_of
enrich_from_detail = news_utils.enrich_from_detail
format_item_line = news_utils.format_item_line
normalize = news_utils.normalize
normalize_urls = news_utils.normalize_urls
now_str = news_utils.now_str
parse_detail_page = news_utils.parse_detail_page
parse_fecha_es = news_utils.parse_fecha_es
resolve_url = news_utils.resolve_url
title_similar = news_utils.title_similar

# Re-exports de compatibilidad (tests y otros importadores usan mod.<helper>).
__all__ = [
    "build_google_news_url",
    "canonical_title",
    "classify",
    "clean_title",
    "clean_url",
    "dedupe",
    "dedupe_by_title",
    "domain_of",
    "enrich_from_detail",
    "enrich_tigres_items",
    "feedparser",
    "fetch_google_news",
    "fetch_tigres_com",
    "fetch_tigres_detail",
    "format_item_line",
    "is_confiable",
    "is_confiable_by_url",
    "is_oficial",
    "listing_time_of",
    "normalize",
    "normalize_urls",
    "now_str",
    "parse_detail_page",
    "parse_fecha_es",
    "resolve_url",
    "smells_like_rumor",
    "title_similar",
]


def is_oficial(url: str) -> bool:
    """Determina si la URL pertenece a un sitio oficial de Tigres.

    Args:
        url: URL a verificar.

    Returns:
        bool: True si el dominio pertenece a SITIOS_OFICIALES.
    """
    return news_utils.is_oficial(url, SITIOS_OFICIALES)


def is_confiable_by_url(url: str) -> bool:
    """Determina si la URL es de un medio confiable (oficial o establecido).

    Args:
        url: URL a verificar.

    Returns:
        bool: True si el dominio está en SITIOS_OFICIALES o SITIOS_CONFIABLES.
    """
    return news_utils.is_confiable_by_url(url, SITIOS_OFICIALES, SITIOS_CONFIABLES)


def is_confiable(source: str, url: str) -> bool:
    """Confiable si el source o el dominio del link es conocido.

    Args:
        source: Nombre de la fuente (ej. 'ESPN').
        url: URL del artículo.

    Returns:
        bool: True si la fuente o dominio es confiable.
    """
    return news_utils.is_confiable(source, url, SITIOS_OFICIALES, SITIOS_CONFIABLES)


def smells_like_rumor(title: str) -> bool:
    """Detecta si un título contiene palabras clave de rumor/filtración.

    Args:
        title: Título de la noticia a analizar.

    Returns:
        bool: True si el título contiene alguna keyword de rumor.
    """
    return news_utils.smells_like_rumor(title, RUMOR_KEYWORDS)


def fetch_google_news(query: str, category: str) -> list:
    """Obtiene noticias de Google News RSS para una consulta.

    Wrapper fino ligado a las constantes de Tigres; la lógica vive en
    news_utils.fetch_google_news.

    Args:
        query: Términos de búsqueda para el feed RSS.
        category: Categoría ('confirmadas' o 'rumores').

    Returns:
        list: Lista de diccionarios con title, link, source, oficial,
        confiable, rumor, origin y category.
    """
    return news_utils.fetch_google_news(
        query, category, SITIOS_OFICIALES, SITIOS_CONFIABLES, RUMOR_KEYWORDS
    )


# ---------------------------------------------------------------------------
# tigres.com.mx scraping
# ---------------------------------------------------------------------------
def listing_time_of(link_tag) -> Optional[datetime]:
    """Fecha del <time> dentro del padre inmediato de un <a> del listado.

    Solo mira el padre inmediato para no contaminar con tarjetas vecinas.

    Args:
        link_tag: Tag <a> de BeautifulSoup.

    Returns:
        datetime o None si la tarjeta no trae fecha.
    """
    parent = getattr(link_tag, "parent", None)
    if parent is None:
        return None
    time_tag = parent.find("time")
    if time_tag is None:
        return None
    dt_attr = time_tag.get("datetime", "")
    if dt_attr:
        parsed = parse_published(dt_attr)
        if parsed is not None:
            return parsed
    return parse_fecha_es(time_tag.get_text(" ", strip=True))


def fetch_tigres_detail(link: str, timeout: int = 10) -> tuple:
    """Extrae fecha real y autor de la página del artículo.

    Lógica en news_utils.parse_detail_page; aquí solo el fetch HTTP.

    Args:
        link: URL del artículo.
        timeout: Timeout HTTP en segundos.

    Returns:
        tuple: (published datetime|None, author str|None).
    """
    try:
        resp = retry_request(link, timeout=timeout, headers=hermes_common.get_headers("default"))
        return parse_detail_page(resp.text)
    except Exception as e:
        logging.warning("Detalle tigres.com.mx falló (%s): %s", link, e)
        return None, None


def enrich_tigres_items(items: list, max_details: int = 12) -> list:
    """Completa autor y confirma fecha visitando el artículo (solo supervivientes).

    Args:
        items: Items de tigres.com.mx ya prefiltrados por fecha del listado.
        max_details: Tope de fetches de detalle por corrida.

    Returns:
        list: Los mismos items con 'author' y 'published' confirmados in-place.
    """
    return enrich_from_detail(items, fetch_tigres_detail, max_details)


def fetch_tigres_com() -> list:
    """Extrae noticias recientes de tigres.com.mx/es/noticias/.

    Cada tarjeta aporta su <time> en español; esa fecha se usa como
    'published' para que el filtro de 48h aplique al sitio oficial.

    Returns:
        list: Lista de diccionarios con title, link, source='tigres.com.mx',
        oficial=True, confiable=True, rumor=False, published (datetime|None),
        author (siempre None aquí; lo completa enrich_tigres_items).
        En caso de error, retorna un solo item con mensaje de error.
    """
    items: list[dict] = []
    url = "https://www.tigres.com.mx/es/noticias/"
    try:
        resp = retry_request(url, timeout=TIMEOUT, headers=hermes_common.get_headers("default"))
        soup = BeautifulSoup(resp.text, "lxml")

        # Sitio WordPress: cada noticia es un <a> cuyo href apunta a /es/noticias/<slug>/
        # (la categoría también matchea /es/noticias/tigres/ etc. — se filtra abajo)
        links = soup.find_all("a", href=re.compile(r"/es/noticias/.+"))
        seen = set()
        for a in links[:40]:
            href = str(a.get("href", "")).strip()
            if not href or href in seen:
                continue
            seen.add(href)

            # Descartar links a listados/categorías (terminan en / o son la lista misma)
            path = href.split("?")[0].rstrip("/")
            if not re.search(r"/es/noticias/[^/]+/[^/]+$", path) and not re.search(
                r"/es/noticias/(?!tigres/?$|club/?$|vlogs/?$|page/)[^/]+$", path
            ):
                continue
            cat_pat = r"/es/noticias/(tigres|tigres-femenil|club|impacto-social|vlogs|page/\d+)/?$"
            if re.search(cat_pat, path):
                continue

            full_link = urljoin(url, href)

            # Título: texto del enlace, atributo title, o heading hermano cercano
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 10:
                title = str(a.get("title", "")).strip()
            if not title or len(title) < 10:
                heading = a.find_next(["h2", "h3", "h4", "h1"])
                if heading:
                    title = heading.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            # Limpiar restos de fecha y "Ver más"
            title = re.sub(r"^\w+ \d{1,2}, \d{4}\s*", "", title)
            title = re.sub(r"\s*Ver más$", "", title).strip()

            # Evitar duplicados por URL
            if str(full_link).rstrip("/") in {str(i["link"]).rstrip("/") for i in items}:
                continue

            items.append(
                {
                    "title": title,
                    "link": full_link,
                    "source": "tigres.com.mx",
                    "oficial": True,
                    "confiable": True,
                    "rumor": False,
                    "origin": "tigres.com.mx",
                    "category": "confirmadas",
                    "published": listing_time_of(a),
                    "author": None,
                }
            )
        return items
    except Exception as e:
        return [
            {
                "title": f"[Error tigres.com.mx: {str(e)[:80]}]",
                "link": "",
                "source": "tigres.com.mx",
                "oficial": False,
                "confiable": False,
                "rumor": False,
                "origin": "tigres.com.mx",
                "category": "confirmadas",
            }
        ]


# ---------------------------------------------------------------------------
# Clasificación y ensamble
# ---------------------------------------------------------------------------
def classify(all_items: list) -> tuple:
    """Clasifica items en confirmadas y rumores (wrapper ligado a Tigres).

    Args:
        all_items: Lista de diccionarios con noticias sin clasificar.

    Returns:
        tuple: (confirmadas, rumores) — dos listas deduplicadas por URL.
    """
    return news_utils.classify(all_items, SITIOS_OFICIALES, SITIOS_CONFIABLES)


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------
def build_report_blocks() -> list:
    """Construye bloques de texto formateados con noticias para envío a Telegram.

    Recolecta noticias de Google News RSS y tigres.com.mx, las clasifica en
    confirmadas y rumores, y las formatea en bloques aptos para el gateway.

    Pipeline:
    1. Inicializa HistoryManager (TTL 72h) para evitar noticias repetidas.
    2. Recolecta de Google News (confirmadas + rumores) y tigres.com.mx.
    2b. Prefiltra tigres.com.mx por fecha del listado (sin fecha = se descarta).
    2c. Enriquece supervivientes oficiales con fecha real y autor del artículo.
    2d. Filtra Google News a 48h (sin fecha = se conserva) y oficiales a 48h.
    3. Filtra por historial — descarta URLs ya enviadas.
    4. Clasifica en confirmadas vs rumores.
    5. Deduplica por título similar.
    6. Construye bloques de texto: encabezado, confirmados, rumores.

    Returns:
        list: Lista de strings, cada uno es un bloque para enviar a Telegram.
        Bloque 0: encabezado, Bloque 1: confirmadas, Bloque 2: rumores.
    """
    history = hermes_common.HistoryManager("~/.hermes/tigres-history.json", ttl_hours=72)

    # 2. Recolectar (con validación)
    google_confirmadas = fetch_google_news(QUERIES["confirmadas"], "confirmadas")
    time.sleep(1)
    google_rumores = fetch_google_news(QUERIES["rumores"], "rumores")
    time.sleep(1)
    tigres_items = fetch_tigres_com()

    # Validar que al menos tenemos datos de tigres.com.mx (fuente más confiable)
    tigres_error = len(tigres_items) == 1 and tigres_items[0].get("title", "").startswith("[Error")
    if tigres_error:
        # tigres.com.mx falló completamente; solo usar Google News
        tigres_items = []
    else:
        # 2b. Prefiltro por fecha del listado: sin fecha verificada no entra.
        tigres_items = filter_by_max_age(tigres_items, missing="drop")
        # 2c. Autor + confirmación de fecha desde el artículo (solo supervivientes).
        enrich_tigres_items(tigres_items)

    # 2d. Ventana de 48h: Google conserva sin-fecha; oficial exige fecha.
    google_items = filter_by_max_age(google_confirmadas + google_rumores)
    tigres_items = filter_by_max_age(tigres_items, missing="drop")
    all_items = google_items + tigres_items

    # 3. Filtrar por historial (Desduplicación Histórica) con URLs normalizadas
    filtered_items = []
    for item in all_items:
        link = item.get("link")
        if link:
            link = clean_url(link)
            item["link"] = link
        if link and history.exists(link):
            continue
        filtered_items.append(item)
        if link:
            history.add(link)

    # 4. Clasificar
    confirmadas, rumores = classify(filtered_items)

    # 5. Dedup por título similar (misma noticia, distinta fuente/URL)
    confirmadas = dedupe_by_title(confirmadas)
    rumores = dedupe_by_title(rumores)

    # 6. Construir bloques para envío fragmentado
    blocks = []

    # Bloque de Encabezado
    header = [
        "🐯 **Tigres UANL — Noticias del día**",
        f"_Actualizado: {now_str()}_",
        "Fuentes: Google News RSS + tigres.com.mx",
    ]
    blocks.append("\n".join(header))

    # Bloque de Confirmados
    mostradas = confirmadas[:MAX_ITEMS_POR_SECCION]
    extra = f" de {len(confirmadas)}" if len(confirmadas) > len(mostradas) else ""
    conf_lines = [
        f"**✅ CONFIRMADO** ({len(mostradas)}{extra})",
        "_Fuentes oficiales y medios establecidos_",
    ]
    if not mostradas:
        conf_lines.append("_No se encontraron noticias confirmadas nuevas en las últimas 48h._\n")
    else:
        for item in mostradas:
            tag = "🎽" if item["oficial"] else "✓"
            link = item.get("link", "")
            conf_lines.append(format_item_line(tag, item, link))
    blocks.append("\n".join(conf_lines))

    # Bloque de Rumores
    mostradas_r = rumores[:MAX_ITEMS_POR_SECCION]
    extra_r = f" de {len(rumores)}" if len(rumores) > len(mostradas_r) else ""
    rum_lines = [
        f"**⚠️ RUMORES** ({len(mostradas_r)}{extra_r})",
        "_No confirmado oficialmente. Tomar con discreción_",
    ]
    if not mostradas_r:
        rum_lines.append("_No se encontraron rumores o filtraciones nuevos en las últimas 48h._\n")
    else:
        for item in mostradas_r:
            link = item.get("link", "")
            rum_lines.append(format_item_line("📰", item, link))
    blocks.append("\n".join(rum_lines))

    return blocks


def main():
    """Punto de entrada: genera y envía reporte de noticias Tigres a Telegram.

    Imprime cada bloque con smart_truncate a TELEGRAM_MAX_CHARS y separador
    '---' entre bloques para que el gateway de Telegram los envíe como
    mensajes independientes.
    """
    blocks = build_report_blocks()
    for block in blocks:
        # Imprimir cada bloque con una separación clara
        # El gateway de Telegram enviará cada print como un mensaje si están separados por tiempo.
        print(hermes_common.smart_truncate(block, limit=TELEGRAM_MAX_CHARS))
        print("\n---\n")  # Separador para el gateway
        time.sleep(1.5)


if __name__ == "__main__":
    main()
