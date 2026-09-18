import json
import logging
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import struct_time
from typing import Any, Dict, Iterable, List, Optional, Union

import requests

_DEFAULT_SESSION = requests.Session()

MAX_RESPONSE_BYTES = 2_000_000


class PayloadTooLargeError(requests.exceptions.RequestException):
    """Body o Content-Length supera MAX_RESPONSE_BYTES."""


def _read_streamed_body(resp, max_bytes):
    """Lee el body de una response en streaming con tope de tamaño.

    Tolerante a mocks: si Content-Length no es un int real, o `iter_content`
    no existe / no es iterable / no yield bytes, se devuelve la response tal
    cual (sin capar) para que `.text` / `.json` / `.content` del caller
    sigan funcionando. Solo se lanza ``PayloadTooLargeError`` y se cierra la
    conexión cuando se detectan bytes reales que superan ``max_bytes``.
    """
    try:
        content_length = int(resp.headers.get("Content-Length"))
    except (AttributeError, TypeError, ValueError):
        content_length = None

    if content_length is not None and content_length > max_bytes:
        resp.close()
        raise PayloadTooLargeError(f"Content-Length {content_length} excede {max_bytes} bytes")

    try:
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                resp.close()
                raise PayloadTooLargeError(f"Body de {total} bytes excede {max_bytes} bytes")
            chunks.append(chunk)
    except (AttributeError, TypeError):
        # Sin iter_content real o iterable: no podés capar, resp intacta.
        return resp

    resp._content = b"".join(chunks)
    resp._content_consumed = True
    return resp


def retry_request(url, timeout=15, max_attempts=3, headers=None, session=None):
    """Fetch URL with exponential backoff + jitter. Retries on transient failures only.

    Args:
        url: URL a solicitar.
        timeout: Timeout en segundos por intento.
        max_attempts: Número máximo de intentos.
        headers: Dict de headers HTTP opcionales. Default: User-Agent estándar.
        session: requests.Session reutilizable. Default: _DEFAULT_SESSION del módulo.

    Returns:
        requests.Response: Respuesta HTTP exitosa, o None si falla silenciosamente.

    Raises:
        requests.ConnectionError: Si se agotan reintentos por error de conexión.
        requests.Timeout: Si se agotan reintentos por timeout.
        requests.HTTPError: Si el status code no es 2xx y no es reintentable.
        PayloadTooLargeError: Si Content-Length o el body excede MAX_RESPONSE_BYTES.
    """
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    sess = session if session is not None else _DEFAULT_SESSION
    retry_status = {429, 500, 502, 503, 504}
    for attempt in range(max_attempts):
        try:
            r = sess.get(url, timeout=timeout, headers=headers, stream=True)
        except (requests.ConnectionError, requests.Timeout):
            if attempt < max_attempts - 1:
                wait = (2**attempt) + random.uniform(0, 0.5)
                time.sleep(wait)
            else:
                raise
            continue
        if r.status_code in retry_status and attempt < max_attempts - 1:
            wait = (2**attempt) + random.uniform(0, 0.5)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return _read_streamed_body(r, MAX_RESPONSE_BYTES)


def premium_link(text: str, url: str) -> str:
    """Returns a markdown formatted link."""
    return f"[{text}]({url})"


LOG_FORMAT = "%(message)s"
LOG_ENV_VAR = "HERMES_LOG_LEVEL"


def setup_logging(level=None):
    """Configura el logger `hermes` hacia stdout (canal de entrega).

    Formato plano: a nivel INFO el output es byte-idéntico al print()
    histórico (el gateway de Telegram consume stdout). Nivel vía
    HERMES_LOG_LEVEL (default INFO). Re-enlaza el handler en cada llamada
    para no retener un sys.stdout viejo (tests con capsys).

    Args:
        level: Nivel explícito (ej. "DEBUG"); si es None usa el env var.

    Returns:
        logging.Logger: El logger `hermes` configurado.
    """
    try:
        resolved = (level or os.environ.get(LOG_ENV_VAR, "INFO")).upper()
        numeric = getattr(logging, resolved, logging.INFO)
        if not isinstance(numeric, int):
            numeric = logging.INFO
    except Exception:
        numeric = logging.INFO
    logger = logging.getLogger("hermes")
    for handler in logger.handlers:
        logger.removeHandler(handler)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(stream)
    logger.setLevel(numeric)
    return logger


def smart_truncate(text: str, limit: int = 3000) -> str:
    """
    Truncates text to limit, attempting to preserve markdown integrity.
    Adds '...' if truncated.
    """
    if len(text) <= limit:
        return text

    limit = limit - 3  # Account for '...'

    # Try to find a safe break point (space or newline) that doesn't split markdown tags
    safe_break = limit
    for i in range(limit, max(0, limit - 200), -1):
        if text[i] in (" ", "\n"):
            # Check for balanced basic markdown in the prefix
            prefix = text[:i]
            if (
                prefix.count("[") == prefix.count("]")
                and prefix.count("(") == prefix.count(")")
                and prefix.count("`") % 2 == 0
                and prefix.count("*") % 2 == 0
                and prefix.count("_") % 2 == 0
            ):
                safe_break = i
                break

    return text[:safe_break].strip() + "..."


def get_headers(store: str) -> Dict[str, str]:
    """Returns request headers for specific stores."""
    common_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"  # noqa: E501

    headers = {
        "User-Agent": common_ua,
        "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    store = store.lower()
    if store == "amazon":
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",  # noqa: E501
                "Device-Memory": "8",
                "Service-Worker-Navigation-Preload": "true",
            }
        )
    elif store == "cyberpuerta":
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",  # noqa: E501
                "Referer": "https://www.cyberpuerta.mx/",
            }
        )
    elif store == "mobile":
        headers["User-Agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"  # noqa: E501
        )

    return headers


class HistoryManager:
    """Manages a history of URLs with TTL to avoid processing duplicates."""

    def __init__(self, filepath: str, ttl_hours: int = 48):
        self.filepath = os.path.expanduser(filepath)
        self.ttl_seconds = ttl_hours * 3600
        self.history = self._load()

    def _load(self) -> Dict[str, float]:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                now = time.time()
                return {url: ts for url, ts in data.items() if now - ts < self.ttl_seconds}
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self):
        """Saves current history to disk."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w") as f:
                json.dump(self.history, f, indent=2)
        except IOError as e:
            logging.warning("History save failed for %s: %s", self.filepath, e)

    def add(self, url: str):
        """Adds a URL to history with current timestamp."""
        self.history[url] = time.time()
        self.save()

    def exists(self, url: str) -> bool:
        """Checks if URL exists and is not expired."""
        if url not in self.history:
            return False

        if time.time() - self.history[url] > self.ttl_seconds:
            del self.history[url]
            self.save()
            return False
        return True

    def filter_new(self, urls: List[str]) -> List[str]:
        """Returns only URLs that are not in history (or have expired)."""
        now = time.time()
        self.history = {url: ts for url, ts in self.history.items() if now - ts < self.ttl_seconds}

        new_urls = [url for url in urls if url not in self.history]
        return new_urls


DEFAULT_NEWS_MAX_AGE_HOURS = 48
_FUTURE_SLACK = timedelta(hours=1)


def _published_from_sequence(value: Any) -> Optional[datetime]:
    """Tupla/lista tipo struct_time desempacado (año..segundo) a UTC."""
    try:
        return datetime(
            int(value[0]),
            int(value[1]),
            int(value[2]),
            int(value[3]),
            int(value[4]),
            int(value[5]),
            tzinfo=timezone.utc,
        )
    except (TypeError, ValueError):
        return None


def _published_from_number(value: Any) -> Optional[datetime]:
    """Epoch (s o ms) a UTC."""
    try:
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _published_from_string(text: str) -> Optional[datetime]:
    """RFC822 o ISO-8601 a UTC. None si no parsea."""
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    iso = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def parse_published(value: Any) -> Optional[datetime]:
    """Normaliza una fecha de publicación a datetime aware UTC.

    Acepta datetime, date, struct_time (feedparser.published_parsed),
    epoch int/float, string RFC822 o ISO-8601. Devuelve None si no parsea.

    Args:
        value: Valor crudo de published / pubDate / updated.

    Returns:
        datetime | None: Fecha en UTC, o None si no se puede interpretar.
    """
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # datetime.date (no datetime)
    if type(value).__name__ == "date" and not isinstance(value, datetime):
        try:
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        except Exception:
            return None

    if isinstance(value, struct_time):
        try:
            return datetime(*value[:6], tzinfo=timezone.utc)
        except Exception:
            return None

    if isinstance(value, (tuple, list)) and len(value) >= 6:
        return _published_from_sequence(value)

    if isinstance(value, (int, float)):
        return _published_from_number(value)

    if isinstance(value, str):
        return _published_from_string(value.strip())

    return None


def is_within_max_age(
    published: Any,
    max_age_hours: int = DEFAULT_NEWS_MAX_AGE_HOURS,
    *,
    now: Optional[datetime] = None,
    missing: str = "keep",
) -> bool:
    """True si published cae en (now - max_age_hours, now + 1h].

    Args:
        published: Fecha cruda o datetime. Se pasa por parse_published.
        max_age_hours: Ventana hacia atrás. Default 48.
        now: Reloj inyectable. Default datetime.now(UTC).
        missing: 'keep' incluye ítems sin fecha; 'drop' los excluye.

    Returns:
        bool: True si el ítem entra en el rango (o missing=keep sin fecha).
    """
    if max_age_hours <= 0:
        raise ValueError("max_age_hours debe ser entero positivo")
    if missing not in ("keep", "drop"):
        raise ValueError("missing debe ser 'keep' o 'drop'")

    parsed = parse_published(published)
    if parsed is None:
        return missing == "keep"

    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)

    oldest = clock - timedelta(hours=max_age_hours)
    newest = clock + _FUTURE_SLACK
    return oldest < parsed <= newest


def filter_by_max_age(
    items: Iterable[Union[dict, Any]],
    max_age_hours: int = DEFAULT_NEWS_MAX_AGE_HOURS,
    *,
    date_keys: Iterable[str] = ("published", "published_parsed", "pubDate", "updated"),
    now: Optional[datetime] = None,
    missing: str = "keep",
) -> List[Any]:
    """Filtra ítems cuya fecha de publicación está fuera del rango.

    Busca la primera clave presente en cada dict (o atributo en objetos).
    Ítems de error (title empieza con '[Error') se conservan siempre.

    Args:
        items: Iterable de dicts o objetos.
        max_age_hours: Ventana hacia atrás. Default 48.
        date_keys: Claves/attrs a inspeccionar, en orden.
        now: Reloj inyectable.
        missing: 'keep' o 'drop' cuando no hay fecha parseable.

    Returns:
        list: Ítems dentro del rango, en el mismo orden.
    """
    keys = tuple(date_keys)
    kept: List[Any] = []
    for item in items:
        title = ""
        if isinstance(item, dict):
            title = str(item.get("title") or "")
        else:
            title = str(getattr(item, "title", "") or "")
        if title.startswith("[Error"):
            kept.append(item)
            continue

        raw = None
        for key in keys:
            if isinstance(item, dict) and key in item and item[key] not in (None, ""):
                raw = item[key]
                break
            if not isinstance(item, dict):
                attr = getattr(item, key, None)
                if attr not in (None, ""):
                    raw = attr
                    break
        if is_within_max_age(raw, max_age_hours, now=now, missing=missing):
            kept.append(item)
    return kept


def repo_root() -> Path:
    """Raíz del repo hermes-scripts (donde viven config/ y CHANGELOG.md).

    El paquete se instala en modo editable, así que ``__file__`` apunta al
    árbol de fuentes: ``src/hermes_common/common.py`` -> ``parents[2]``.
    Mismo criterio que ``src/install_cron.py``.

    Returns:
        Path: directorio del repo.
    """
    return Path(__file__).resolve().parents[2]


def get_repo_version(repo_root=None):
    """Devuelve el último tag semántico del repo (para sellar reportes).

    Args:
        repo_root: Directorio del repo (default: cwd del proceso).

    Returns:
        str: Último tag vía `git describe --tags --abbrev=0`, o `'dev'`
        si no hay tag/repo/git. Nunca lanza excepción.
    """
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=repo_root,
        )
        tag = result.stdout.strip()
        if result.returncode == 0 and tag:
            return tag
    except Exception:
        pass
    return "dev"
