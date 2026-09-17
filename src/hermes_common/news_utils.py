"""news_utils.py — helpers compartidos de noticias.

Extraídos de resumen-tigres-diario.py, resumen-rayados-diario.py y
resumen-noticias-diario.py (issue #70). Funciones puras sin estado global.
Las funciones que dependen de la
configuración por equipo (dominios, keywords) reciben esas listas como
parámetros; cada script las liga con sus constantes en wrappers finos.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Optional
from urllib.parse import quote

import requests

from .common import parse_published

# Telegram: límite de un mensaje = 4096 caracteres; dejamos margen para cabeceras de formato.
TELEGRAM_MAX_CHARS = 3000

# Máximo de items que se muestran por sección (confirmadas / rumores)
MAX_ITEMS_POR_SECCION = 8


@dataclass
class NewsItem:
    """Noticia tipada del pipeline (issue #73).

    Reemplaza los dicts informales: los productores la construyen y los
    helpers la consumen por atributo.
    """

    title: str = ""
    link: str = ""
    source: str = ""
    oficial: bool = False
    confiable: bool = False
    rumor: bool = False
    origin: str = ""
    category: str = ""
    published: Optional[datetime] = None
    author: Optional[str] = None


def now_str() -> str:
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
        str: Dominio limpio.
    """
    url = normalize(url)
    parts = url.split("/")
    if not parts:
        return ""
    host = parts[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def is_oficial(url: str, sitios_oficiales: list) -> bool:
    """Determina si la URL pertenece a un sitio oficial.

    Args:
        url: URL a verificar.
        sitios_oficiales: Dominios oficiales del equipo.

    Returns:
        bool: True si el dominio pertenece a sitios_oficiales.
    """
    return any(d in domain_of(url) for d in sitios_oficiales)


def is_confiable_by_url(url: str, sitios_oficiales: list, sitios_confiables: list) -> bool:
    """Determina si la URL es de un medio confiable (oficial o establecido).

    Args:
        url: URL a verificar.
        sitios_oficiales: Dominios oficiales del equipo.
        sitios_confiables: Dominios de medios establecidos.

    Returns:
        bool: True si el dominio está en alguna de las listas.
    """
    return is_oficial(url, sitios_oficiales) or any(d in domain_of(url) for d in sitios_confiables)


def is_confiable(source: str, url: str, sitios_oficiales: list, sitios_confiables: list) -> bool:
    """Confiable si el source o el dominio del link es conocido.

    Args:
        source: Nombre de la fuente (ej. 'ESPN').
        url: URL del artículo.
        sitios_oficiales: Dominios oficiales del equipo.
        sitios_confiables: Dominios de medios establecidos.

    Returns:
        bool: True si la fuente o dominio es confiable.
    """
    source_clean = source.lower()
    if any(d in source_clean for d in sitios_oficiales + sitios_confiables):
        return True
    return is_confiable_by_url(url, sitios_oficiales, sitios_confiables)


def smells_like_rumor(title: str, rumor_keywords: list) -> bool:
    """Detecta si un título contiene palabras clave de rumor/filtración.

    Args:
        title: Título de la noticia a analizar.
        rumor_keywords: Palabras que indican rumor.

    Returns:
        bool: True si el título contiene alguna keyword de rumor.
    """
    t = title.lower()
    return any(kw in t for kw in rumor_keywords)


def dedupe(items: list[NewsItem], key: Callable = lambda x: x.link or x.title) -> list[NewsItem]:
    """Elimina duplicados conservando el orden. Usa URL normalizada.

    Args:
        items: Lista de NewsItem.
        key: Función para extraer la clave de deduplicación.

    Returns:
        list[NewsItem]: Lista sin duplicados, orden original conservado.
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


def clean_url(url: str, *, escape_parens: bool = False) -> str:
    """Quita tracking params y normaliza URL Google News.

    Args:
        url: URL a limpiar.
        escape_parens: Si True, escapa ')' como '%29' (Markdown).

    Returns:
        str: URL sin parámetros de tracking (oc, utm_, ceid).
    """
    url = re.sub(r"[?&]oc=\d+", "", url)
    url = re.sub(r"[?&]utm_[^&]+", "", url)
    url = re.sub(r"[?&]ceid=[^&]+", "", url)
    url = url.rstrip("?&")
    if escape_parens:
        url = url.replace(")", "%29")
    return url


def canonical_title(title: str) -> str:
    """Clave canónica de un titular: minúsculas + solo [a-záéíóúñ0-9].

    Args:
        title: Título a normalizar.

    Returns:
        str: Título normalizado ("" si no queda nada).
    """
    return re.sub(r"[^a-záéíóúñ0-9]", "", (title or "").lower())


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
    a = canonical_title(t1)
    b = canonical_title(t2)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() > threshold


def dedupe_by_title(
    items: list[NewsItem], threshold: float = 0.85, bucket_chars: int = 12
) -> list[NewsItem]:
    """Elimina items con títulos muy similares (misma noticia, distinta URL).

    Exactos por hash canónico O(1); casi-duplicados por cubetas de prefijo
    (solo se compara dentro de la cubeta, no contra todo lo visto). Lineal
    en la práctica; el peor caso (todo en una cubeta) degrada al O(n²) previo.

    Args:
        items: Lista de NewsItem.
        threshold: Umbral de similitud para title_similar. Con >= 1.0 solo
            colapsan canónicos idénticos (ruta puramente lineal).
        bucket_chars: Prefijo canónico que define cada cubeta.

    Returns:
        list[NewsItem]: Lista sin duplicados por título, conserva el primero.
    """
    if threshold >= 1.0:
        seen: set[str] = set()
        exact: list[NewsItem] = []
        for item in items:
            key = canonical_title(item.title)
            if not key:
                exact.append(item)
            elif key not in seen:
                seen.add(key)
                exact.append(item)
        return exact
    seen_keys: set[str] = set()
    buckets: dict[str, list[NewsItem]] = {}
    out: list[NewsItem] = []
    for item in items:
        title = item.title
        key = canonical_title(title)
        if not key:
            out.append(item)
            continue
        if key in seen_keys:
            continue
        bucket = buckets.setdefault(key[:bucket_chars], [])
        if any(title_similar(title, kept.title, threshold) for kept in bucket):
            continue
        seen_keys.add(key)
        bucket.append(item)
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


def normalize_urls(items: list[NewsItem]) -> list[NewsItem]:
    """Normaliza URLs de todos los items in-place.

    Args:
        items: Lista de NewsItem.

    Returns:
        list[NewsItem]: La misma lista con URLs normalizadas vía clean_url.
    """
    for item in items:
        if item.link:
            item.link = clean_url(item.link)
    return items


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
    except Exception as e:
        logging.warning("resolve_url failed: %s", e)
    return google_news_url


def build_google_news_url(query: str) -> str:
    """Construye URL de Google News RSS para una consulta.

    Args:
        query: Términos de búsqueda para Google News.

    Returns:
        str: URL completa del feed RSS de Google News (es-419, MX).
    """
    encoded = quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=es-419&gl=MX&ceid=MX:es-419"


def fetch_google_news(
    query: str,
    category: str,
    sitios_oficiales: list,
    sitios_confiables: list,
    rumor_keywords: list,
) -> list:
    """Obtiene noticias de Google News RSS para una consulta.

    Args:
        query: Términos de búsqueda para el feed RSS.
        category: Categoría ('confirmadas' o 'rumores').
        sitios_oficiales: Dominios oficiales del equipo.
        sitios_confiables: Dominios de medios establecidos.
        rumor_keywords: Palabras que indican rumor.

    Returns:
        list[NewsItem]: Lista de NewsItem. En caso de error, retorna
        un solo item con mensaje de error.
    """
    import feedparser

    items: list[NewsItem] = []
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
            oficial = is_oficial(link, sitios_oficiales)
            confiable = is_confiable(source, link, sitios_oficiales, sitios_confiables)
            rumor = smells_like_rumor(title, rumor_keywords)

            items.append(
                NewsItem(
                    title=title,
                    link=link,
                    source=source,
                    oficial=oficial,
                    confiable=confiable,
                    rumor=rumor,
                    origin="google-news",
                    category=category,
                    published=parse_published(
                        entry.get("published_parsed")
                        or entry.get("published")
                        or entry.get("updated")
                    ),
                )
            )
        return items
    except Exception as e:
        return [
            NewsItem(
                title=f"[Error Google News ({category}): {str(e)[:80]}]",
                origin="google-news",
                category=category,
            )
        ]


def classify(all_items: list, sitios_oficiales: list, sitios_confiables: list) -> tuple:
    """Clasifica items en confirmadas y rumores.

    Criterios de clasificación:
    - Items con 'origin' que empieza con 'Error' → confirmadas (visibles).
    - Items oficiales → confirmadas.
    - Items de categoría 'rumores' o con flag 'rumor' → rumores.
    - Items confiables (medios establecidos) → confirmadas.
    - Resto (fuente desconocida, título objetivo) → confirmadas.

    Args:
        all_items: Lista de NewsItem sin clasificar.
        sitios_oficiales: Dominios oficiales del equipo.
        sitios_confiables: Dominios de medios establecidos.

    Returns:
        tuple: (confirmadas, rumores) — dos listas deduplicadas por URL.
    """
    confirmadas = []
    rumores = []

    for item in all_items:
        if item.origin.startswith("Error"):
            # Mensajes de error van a confirmadas para que sean visibles
            confirmadas.append(item)
            continue

        if item.oficial:
            confirmadas.append(item)
            continue

        # Si venía de la query de rumores o el título suena a rumor, va a rumores
        if item.category == "rumores" or item.rumor:
            rumores.append(item)
            continue

        # Lo que queda es de la query de confirmadas
        if item.confiable:
            confirmadas.append(item)
        else:
            # Fuente desconocida pero título objetivo: reportar como confirmada
            confirmadas.append(item)

    return dedupe(confirmadas), dedupe(rumores)


def format_item_line(tag: str, item: NewsItem, link: str) -> str:
    """Formatea una línea de reporte con fecha y autor cuando existen.

    Args:
        tag: Emoji/prefijo (ej. '🎽' o '✓').
        item: NewsItem (usa 'title', 'source', opcional 'published' datetime
            y 'author').
        link: URL del item (puede ser vacía).

    Returns:
        str: Línea Markdown para Telegram.
    """
    title = clean_title(item.title)
    fecha = ""
    published = item.published
    if isinstance(published, datetime):
        pub = published
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        fecha = f" ({pub.strftime('%Y-%m-%d')})"
    autor = f" — por {item.author}" if item.author else ""
    head = f"- {tag} **{item.source}**{fecha}: "
    if link:
        return f"{head}[{title}]({link}){autor}"
    return f"{head}{title}{autor}"


def enrich_from_detail(
    items: list[NewsItem],
    fetch_detail: Callable[[str], tuple],
    max_details: int = 12,
) -> list[NewsItem]:
    """Completa autor y confirma fecha visitando el artículo.

    Genérico sobre fetch_detail para no duplicar el loop por equipo.

    Args:
        items: Items ya prefiltrados por fecha.
        fetch_detail: Función (link) -> (published|None, author|None).
        max_details: Tope de fetches de detalle por corrida.

    Returns:
        list: Los mismos items con 'author' y 'published' confirmados in-place.
    """
    for item in items[:max_details]:
        link = item.link
        if not link:
            continue
        published, author = fetch_detail(link)
        if published is not None:
            item.published = published
        if author and not item.author:
            item.author = author
    return items


def parse_fecha_es(text: str) -> Optional[datetime]:
    """Interpreta fecha en español ('septiembre 12, 2026').

    Args:
        text: Texto crudo de fecha en español.

    Returns:
        datetime aware UTC con día de publicación, o None si no parsea.
    """
    meses = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    if not text or not text.strip():
        return None
    t = text.strip().lower()
    m = re.search(r"([a-záéíóúñ]+)\s+(\d{1,2}),?\s+(\d{4})", t)
    if m:
        mes = meses.get(m.group(1))
        if mes:
            try:
                return datetime(int(m.group(3)), mes, int(m.group(2)), tzinfo=timezone.utc)
            except ValueError:
                return None
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})", t)
    if m:
        mes = meses.get(m.group(2))
        if mes:
            try:
                return datetime(int(m.group(3)), mes, int(m.group(1)), tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


def parse_detail_page(html: str) -> tuple:
    """Extrae (published, author) del HTML de un artículo.

    Orden: meta article:published_time → JSON-LD datePublished →
    meta name author / JSON-LD author.name.

    Args:
        html: HTML crudo del artículo.

    Returns:
        tuple: (published datetime|None, author str|None).
    """
    import json

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    published = None
    author: Optional[str] = None
    meta_pub = soup.find("meta", attrs={"property": "article:published_time"})
    if meta_pub and meta_pub.get("content"):
        published = parse_published(str(meta_pub.get("content")))
    if published is None:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.get_text() or "")
            except (ValueError, TypeError):
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                graph = node.get("@graph", [node])
                if not isinstance(graph, list):
                    graph = [graph]
                for entry in graph:
                    if not isinstance(entry, dict):
                        continue
                    if published is None and entry.get("datePublished"):
                        published = parse_published(entry.get("datePublished"))
                    if author is None:
                        auth: Any = entry.get("author")
                        if isinstance(auth, dict) and auth.get("name"):
                            author = str(auth["name"]).strip()
                        elif isinstance(auth, str) and auth.strip():
                            author = auth.strip()
                if published is not None and author is not None:
                    break
    if author is None:
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = str(meta_author.get("content")).strip() or None
    return published, author
