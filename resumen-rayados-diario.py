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

import os
import re
import sys
import time
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import quote, urljoin

sys.path.append(os.path.dirname(__file__))
import hermes_common
from hermes_common import retry_request

# Cron job uses the Hermes venv by default; ensure deps are installed if missing.
try:
    import feedparser
    import requests
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    import subprocess

    uv = os.environ.get("UV", "/home/d13g0m0r3n0/.local/bin/uv")
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
    import feedparser
    import requests
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
# Helpers
# ---------------------------------------------------------------------------
def now_str():
    """Devuelve timestamp actual con zona horaria para el reporte.

    Returns:
        str: Fecha y hora en formato 'YYYY-MM-DD HH:MM TZ'.
    """
    tz = datetime.now().astimezone().tzname() or "hora local"
    return f"{datetime.now().strftime('%Y-%m-%d %H:%M')} {tz}"

def normalize(url: str) -> str:
    """Limpia URL para comparación de dominio.

    Args:
        url: URL a normalizar.

    Returns:
        str: URL sin protocolo, en minúsculas.
    """
    url = url.strip().lower()
    if url.startswith("http://"):
        url = url[7:]
    elif url.startswith("https://"):
        url = url[8:]
    return url

def domain_of(url: str) -> str:
    """Extrae el dominio de una URL (sin protocolo ni www).

    Args:
        url: URL de la cual extraer el dominio.

    Returns:
        str: Dominio limpio, ej. 'rayados.com'.
    """
    url = normalize(url)
    parts = url.split("/")
    if not parts:
        return ""
    host = parts[0]
    if host.startswith("www."):
        host = host[4:]
    return host

def is_oficial(url: str) -> bool:
    """Determina si la URL pertenece a un sitio oficial de Rayados.

    Args:
        url: URL a verificar.

    Returns:
        bool: True si el dominio pertenece a SITIOS_OFICIALES.
    """
    return any(d in domain_of(url) for d in SITIOS_OFICIALES)

def is_confiable_by_url(url: str) -> bool:
    """Determina si la URL es de un medio confiable (oficial o establecido).

    Args:
        url: URL a verificar.

    Returns:
        bool: True si el dominio está en SITIOS_OFICIALES o SITIOS_CONFIABLES.
    """
    return is_oficial(url) or any(d in domain_of(url) for d in SITIOS_CONFIABLES)

def is_confiable(source: str, url: str) -> bool:
    """Confiable si el source o el dominio del link es conocido.

    Args:
        source: Nombre de la fuente (ej. 'ESPN').
        url: URL del artículo.

    Returns:
        bool: True si la fuente o dominio es confiable.
    """
    source_clean = source.lower()
    if any(d in source_clean for d in SITIOS_OFICIALES + SITIOS_CONFIABLES):
        return True
    return is_confiable_by_url(url)

def smells_like_rumor(title: str) -> bool:
    """Detecta si un título contiene palabras clave de rumor/filtración.

    Args:
        title: Título de la noticia a analizar.

    Returns:
        bool: True si el título contiene alguna keyword de rumor.
    """
    t = title.lower()
    return any(kw in t for kw in RUMOR_KEYWORDS)

def dedupe(items, key=lambda x: x["link"] or x["title"]):
    """Elimina duplicados conservando el orden. Usa URL normalizada.

    Args:
        items: Lista de diccionarios con noticias.
        key: Función lambda para extraer la clave de deduplicación.

    Returns:
        list: Lista sin duplicados, orden original conservado.
    """
    seen = set()
    out = []
    for item in items:
        k = key(item)
        if k:
            k = clean_url(k)
        if k and k not in seen:
            seen.add(k)
            out.append(item)
    return out

def clean_url(url: str) -> str:
    """Quita tracking params y normaliza URL Google News.

    Args:
        url: URL a limpiar.

    Returns:
        str: URL sin parámetros de tracking (oc, utm_, ceid).
    """
    url = re.sub(r"[?&]oc=\d+", "", url)
    url = re.sub(r"[?&]utm_[^&]+", "", url)
    url = re.sub(r"[?&]ceid=[^&]+", "", url)
    return url.rstrip("?&")

def title_similar(t1: str, t2: str, threshold: float = 0.85) -> bool:
    """Dos titulares son suficientemente similares (misma noticia).

    Args:
        t1: Primer título.
        t2: Segundo título.
        threshold: Umbral de similitud SequenceMatcher (0.0 a 1.0).

    Returns:
        bool: True si la similitud supera el threshold.
    """
    if not t1 or not t2:
        return False
    a = re.sub(r"[^a-záéíóúñ0-9]", "", t1.lower())
    b = re.sub(r"[^a-záéíóúñ0-9]", "", t2.lower())
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() > threshold

def dedupe_by_title(items, threshold: float = 0.85):
    """Elimina items con títulos muy similares (misma noticia, distinta URL).

    Args:
        items: Lista de diccionarios con clave 'title'.
        threshold: Umbral de similitud para title_similar.

    Returns:
        list: Lista sin duplicados por título, conserva el primero.
    """
    out = []
    for item in items:
        title = item.get("title", "")
        if not any(title_similar(title, existing.get("title", ""), threshold) for existing in out):
            out.append(item)
    return out

def clean_title(title: str) -> str:
    """Limpia título: quita source suffix, escapa [] para Markdown.

    Args:
        title: Título de la noticia.

    Returns:
        str: Título sin sufijo de fuente y con brackets escapados.
    """
    # Quitar " - SourceName" al final
    title = title.split(" - ")[0].strip()
    # Reemplazar brackets que rompen markdown
    title = title.replace("[", "(").replace("]", ")")
    return title

def normalize_urls(items):
    """Normaliza URLs de todos los items in-place.

    Args:
        items: Lista de diccionarios con clave 'link'.

    Returns:
        list: La misma lista con URLs normalizadas vía clean_url.
    """
    for item in items:
        if item.get("link"):
            item["link"] = clean_url(item["link"])
    return items

# Cache global para URLs acortadas
_URL_CACHE = {}

def shorten_url(long_url, timeout=5):
    """Acorta URL con TinyURL (gratis, sin API key). Cachea resultados.

    Args:
        long_url: URL larga a acortar.
        timeout: Timeout HTTP en segundos.

    Returns:
        str: URL acortada si es de Google News; la URL original si no.
    """
    if "news.google.com" not in long_url:
        return long_url
    if long_url in _URL_CACHE:
        return _URL_CACHE[long_url]
    try:
        r = retry_request(
            f"https://tinyurl.com/api-create.php?url={quote(long_url, safe='')}",
            timeout=timeout,
        )
        if r.status_code == 200 and r.text.startswith("http"):
            short = r.text.strip()
            _URL_CACHE[long_url] = short
            return short
    except Exception:
        pass
    return long_url

def resolve_url(google_news_url: str, timeout: int = 5) -> str:
    """Resuelve redirect de Google News a URL real del artículo.

    Args:
        google_news_url: URL de Google News a resolver.
        timeout: Timeout HTTP en segundos.

    Returns:
        str: URL final tras redirects, o la original si falla la resolución.
    """
    if "news.google.com" not in google_news_url:
        return google_news_url
    try:
        resp = requests.head(
            google_news_url,
            allow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        final = resp.url
        if final and final != google_news_url and "news.google.com" not in final:
            return final
    except Exception:
        pass
    return google_news_url

# ---------------------------------------------------------------------------
# Google News RSS
# ---------------------------------------------------------------------------
def build_google_news_url(query: str) -> str:
    """Construye URL de Google News RSS para una consulta.

    Args:
        query: Términos de búsqueda para Google News.

    Returns:
        str: URL completa del feed RSS de Google News (es-419, MX).
    """
    encoded = quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=es-419&gl=MX&ceid=MX:es-419"

def fetch_google_news(query: str, category: str) -> list:
    """Obtiene noticias de Google News RSS para una consulta.

    Args:
        query: Términos de búsqueda para el feed RSS.
        category: Categoría ('confirmadas' o 'rumores').

    Returns:
        list: Lista de diccionarios con title, link, source, oficial,
        confiable, rumor, origin y category. En caso de error, retorna
        un solo item con mensaje de error.
    """
    items = []
    try:
        url = build_google_news_url(query)
        feed = feedparser.parse(url)
        for entry in feed.entries[:15]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            source = (
                getattr(entry, "source", {}).get("title", "") if hasattr(entry, "source") else ""
            )
            if not source:
                source = entry.get("author", "Google News")
            if not title:
                continue

            # Google News RSS a veces redirige; intentamos conservar URL original
            if not link and entry.get("id"):
                link = entry.get("id")

            # El source es el medio real; limpiar título de Google News si trae el sufijo
            for suffix in (f" - {source}", f" - {source.strip()}"):
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()

            # Determinar confiabilidad y categoría
            oficial = is_oficial(link)
            confiable = is_confiable(source, link)
            rumor = smells_like_rumor(title)

            items.append(
                {
                    "title": title,
                    "link": link,
                    "source": source,
                    "oficial": oficial,
                    "confiable": confiable,
                    "rumor": rumor,
                    "origin": "google-news",
                    "category": category,
                }
            )
        return items
    except Exception as e:
        return [
            {
                "title": f"[Error Google News ({category}): {str(e)[:80]}]",
                "link": "",
                "source": "",
                "oficial": False,
                "confiable": False,
                "rumor": False,
                "origin": "google-news",
                "category": category,
            }
        ]

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
            href = a.get("href", "").strip()
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
                title = a.get("title", "").strip()
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
    """Clasifica items en confirmadas y rumores.

    Criterios de clasificación:
    - Items con 'origin' que empieza con 'Error' → confirmadas (visibles).
    - Items oficiales → confirmadas.
    - Items de categoría 'rumores' o con flag 'rumor' → rumores.
    - Items confiables (medios establecidos) → confirmadas.
    - Resto (fuente desconocida, título objetivo) → confirmadas.

    Args:
        all_items: Lista de diccionarios con noticias sin clasificar.

    Returns:
        tuple: (confirmadas, rumores) — dos listas deduplicadas por URL.
    """
    confirmadas = []
    rumores = []

    for item in all_items:
        if item["origin"].startswith("Error"):
            # Mensajes de error van a confirmadas para que sean visibles
            confirmadas.append(item)
            continue

        if item["oficial"]:
            confirmadas.append(item)
            continue

        # Si venía de la query de rumores o el título suena a rumor, va a rumores
        if item["category"] == "rumores" or item["rumor"]:
            rumores.append(item)
            continue

        # Lo que queda es de la query de confirmadas
        if item["confiable"]:
            confirmadas.append(item)
        else:
            # Fuente desconocida pero título objetivo: reportar como confirmada
            confirmadas.append(item)

    return dedupe(confirmadas), dedupe(rumores)

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
            title = clean_title(item["title"])
            link = shorten_url(item.get("link", ""))
            if link:
                conf_lines.append(f"- {tag} **{item['source']}**: [{title}]({link})")
            else:
                conf_lines.append(f"- {tag} **{item['source']}**: {title}")
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
            title = clean_title(item["title"])
            link = shorten_url(item.get("link", ""))
            if link:
                rum_lines.append(f"- **{item['source']}**: [{title}]({link})")
            else:
                rum_lines.append(f"- **{item['source']}**: {title}")
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
