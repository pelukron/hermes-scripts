#!/usr/bin/env python3
"""
resumen-rayados-diario.py
Recopila noticias de Rayados de Monterrey para un resumen diario en Telegram.
Fuentes:
  1) Google News RSS México (palabras clave de Rayados).
  2) Sitio oficial rayados.com (noticias recientes).

Divide resultados en:
  - Noticias confirmadas (medios establecidos y sitio oficial).
  - Rumores/filtraciones (con disclaimer de no confirmación).

Uso:
  ~/.hermes/venv/bin/python ~/.hermes/scripts/resumen-rayados-diario.py
"""

import logging
import os
import re
import sys
import time
from urllib.parse import urljoin

sys.path.append(os.path.dirname(__file__))
import hermes_common
from hermes_common import filter_by_max_age, news_utils, retry_request

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

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
TIMEOUT = 20

# Palabras clave para cada categoría en Google News RSS México
QUERIES = {
    "confirmadas": '"Rayados de Monterrey" OR "Club de Fútbol Monterrey"',
    "rumores": (
        '"Rayados" AND (fichaje OR rumor OR filtración OR "mercado de pases" '
        "OR transferencia OR lesionado OR baja OR venta)"
    ),
}

# Dominios considerados medios establecidos / fuentes oficiales
SITIOS_OFICIALES = ["rayados.com", "rayados.mx"]
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
# Aquí solo quedan wrappers finos ligados a las constantes de Rayados.
# Los alias directos mantienen compatibilidad con mod.<helper>.
# ---------------------------------------------------------------------------
build_google_news_url = news_utils.build_google_news_url
canonical_title = news_utils.canonical_title
clean_title = news_utils.clean_title
clean_url = news_utils.clean_url
dedupe = news_utils.dedupe
dedupe_by_title = news_utils.dedupe_by_title
domain_of = news_utils.domain_of
format_item_line = news_utils.format_item_line
normalize = news_utils.normalize
normalize_urls = news_utils.normalize_urls
now_str = news_utils.now_str
resolve_url = news_utils.resolve_url
shorten_url = news_utils.shorten_url
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
    "feedparser",
    "fetch_google_news",
    "fetch_rayados_com",
    "format_item_line",
    "is_confiable",
    "is_confiable_by_url",
    "is_oficial",
    "normalize",
    "normalize_urls",
    "now_str",
    "resolve_url",
    "shorten_url",
    "smells_like_rumor",
    "title_similar",
]


def is_oficial(url: str) -> bool:
    """Determina si la URL pertenece a un sitio oficial de Rayados.

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


# ---------------------------------------------------------------------------
# Google News RSS
# ---------------------------------------------------------------------------
def fetch_google_news(query: str, category: str) -> list:
    """Obtiene noticias de Google News RSS para una consulta.

    Wrapper fino ligado a las constantes de Rayados; la lógica vive en
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
# rayados.com scraping
# ---------------------------------------------------------------------------
def fetch_rayados_com() -> list:
    """Extrae noticias recientes de rayados.com/es/noticias/lista.

    Returns:
        list: Lista de diccionarios con title, link, source='rayados.com',
        oficial=True, confiable=True, rumor=False. En caso de error, retorna
        un solo item con mensaje de error.
    """
    items = []
    url = "https://rayados.com/es/noticias/lista"
    try:
        resp = retry_request(url, timeout=TIMEOUT, headers=hermes_common.get_headers("default"))
        soup = BeautifulSoup(resp.text, "lxml")

        # La página lista cada noticia en un <li> con heading y link "Noticia NNN"
        list_items = soup.find_all("li")
        seen = set()
        for li in list_items[:20]:
            # Buscar el enlace a la noticia (el link con texto "Noticia <id>")
            a = li.find("a", href=re.compile(r"/es/noticias/\d+(/|\?|$)"))
            if not a:
                continue
            href = str(a.get("href", "")).strip()
            if not href or href in seen:
                continue
            seen.add(href)

            full_link = urljoin(url, href)

            # Extraer el título del heading dentro del <li>
            title = ""
            heading = li.find(["h2", "h3", "h4", "h1"])
            if heading:
                title = heading.get_text(strip=True)
            if not title:
                title = str(a.get("title", "")).strip()
            if not title or len(title) < 10:
                continue

            # Evitar duplicados por URL
            if full_link in seen:
                continue
            seen.add(full_link)

            items.append(
                {
                    "title": title,
                    "link": full_link,
                    "source": "rayados.com",
                    "oficial": True,
                    "confiable": True,
                    "rumor": False,
                    "origin": "rayados.com",
                    "category": "confirmadas",
                }
            )
        return items
    except Exception as e:
        return [
            {
                "title": f"[Error rayados.com: {str(e)[:80]}]",
                "link": "",
                "source": "rayados.com",
                "oficial": False,
                "confiable": False,
                "rumor": False,
                "origin": "rayados.com",
                "category": "confirmadas",
            }
        ]


# ---------------------------------------------------------------------------
# Clasificación y ensamble
# ---------------------------------------------------------------------------
def classify(all_items: list) -> tuple:
    """Clasifica items en confirmadas y rumores (wrapper ligado a Rayados).

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

    Recolecta noticias de Google News RSS y rayados.com, las clasifica en
    confirmadas y rumores, y las formatea en bloques aptos para el gateway.

    Pipeline:
    1. Inicializa HistoryManager (TTL 72h) para evitar noticias repetidas.
    2. Recolecta de Google News (confirmadas + rumores) y rayados.com.
    3. Filtra por historial — descarta URLs ya enviadas.
    4. Clasifica en confirmadas vs rumores.
    5. Deduplica por título similar.
    6. Construye bloques de texto: encabezado, confirmados, rumores.

    Returns:
        list: Lista de strings, cada uno es un bloque para enviar a Telegram.
        Bloque 0: encabezado, Bloque 1: confirmadas, Bloque 2: rumores.
    """
    history = hermes_common.HistoryManager("~/.hermes/rayados-history.json", ttl_hours=72)

    # 2. Recolectar (con validación)
    google_confirmadas = fetch_google_news(QUERIES["confirmadas"], "confirmadas")
    time.sleep(1)
    google_rumores = fetch_google_news(QUERIES["rumores"], "rumores")
    time.sleep(1)
    rayados_items = fetch_rayados_com()

    # Validar que al menos tenemos datos de rayados.com (fuente más confiable)
    rayados_error = len(rayados_items) == 1 and rayados_items[0].get("title", "").startswith(
        "[Error"
    )
    if rayados_error:
        # rayados.com falló completamente; solo usar Google News
        all_items = google_confirmadas + google_rumores
    else:
        all_items = google_confirmadas + google_rumores + rayados_items

    # 2b. Tirar notas fuera de la ventana de 48h (sin fecha = se quedan)
    all_items = filter_by_max_age(all_items)

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
        "⚽ **Rayados de Monterrey — Noticias del día**",
        f"_Actualizado: {now_str()}_",
        "Fuentes: Google News RSS + rayados.com",
    ]
    blocks.append("\n".join(header))

    # Bloque de Confirmados
    conf_lines = [
        f"**✅ CONFIRMADO** ({len(confirmadas)})",
        "_Fuentes oficiales y medios establecidos_",
    ]
    if not confirmadas:
        conf_lines.append("_No se encontraron noticias confirmadas nuevas en las últimas 48h._\n")
    else:
        for item in confirmadas[:8]:
            tag = "🎽" if item["oficial"] else "✓"
            link = shorten_url(item.get("link", ""))
            conf_lines.append(format_item_line(tag, item, link))
    blocks.append("\n".join(conf_lines))

    # Bloque de Rumores
    rum_lines = [
        f"**⚠️ RUMORES** ({len(rumores)})",
        "_No confirmado oficialmente. Tomar con discreción_",
    ]
    if not rumores:
        rum_lines.append("_No se encontraron rumores o filtraciones nuevos en las últimas 48h._\n")
    else:
        for item in rumores[:8]:
            link = shorten_url(item.get("link", ""))
            rum_lines.append(format_item_line("📰", item, link))
    blocks.append("\n".join(rum_lines))

    return blocks


def main():
    """Punto de entrada: genera y envía reporte de noticias Rayados a Telegram.

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
