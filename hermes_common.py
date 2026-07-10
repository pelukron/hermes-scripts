import json
import os
import time
from typing import Dict, List, Optional


def premium_link(text: str, url: str) -> str:
    """Returns a markdown formatted link."""
    return f"[{text}]({url})"


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
    common_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    headers = {
        "User-Agent": common_ua,
        "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    store = store.lower()
    if store == "amazon":
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Device-Memory": "8",
                "Service-Worker-Navigation-Preload": "true",
            }
        )
    elif store == "cyberpuerta":
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Referer": "https://www.cyberpuerta.mx/",
            }
        )
    elif store == "mobile":
        headers["User-Agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
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
                # Filter expired items
                return {url: ts for url, ts in data.items() if now - ts < self.ttl_seconds}
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self):
        """Saves current history to disk."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w") as f:
                json.dump(self.history, f, indent=2)
        except IOError:
            pass

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
        # Pre-clean
        self.history = {url: ts for url, ts in self.history.items() if now - ts < self.ttl_seconds}

        new_urls = [url for url in urls if url not in self.history]
        return new_urls
