#!/usr/bin/env python3
"""Diario Global Hermes — fuentes multiregión, multi-ideología."""

import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

import defusedxml.ElementTree as ET  # noqa: N817

from hermes_common import news_utils, retry_request

# Helpers compartidos en src/hermes_common/news_utils.py (issue #70).
clean_title = news_utils.clean_title

# Re-exports de compatibilidad (tests y otros importadores usan mod.<helper>).
__all__ = [
    "clean_title",
    "escape_link",
    "fetch_all_rss",
    "fetch_crypto",
    "fetch_currencies",
    "fetch_rss",
    "load_feeds",
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, path)
    with open(full_path) as f:
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


def main():
    print(f"🪨 **DIARIO GLOBAL HERMES** 🪨\n_Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")
    time.sleep(0.5)

    feeds = load_feeds()
    for section_name, subsections in feeds:
        section_has_content = False
        section_lines = [f"**{section_name}**"]

        for sub_name, sources in subsections:
            sub_lines = []
            sub_has_content = False

            fetched = fetch_all_rss(sources)
            for (source_name, url), items in zip(sources, fetched):
                if not items:
                    continue

                if not sub_has_content:
                    sub_lines.append(f"_{sub_name}_")
                    sub_has_content = True
                source_lines = [f"• *{source_name}*"]
                for title, link in items[:1]:  # 1 item por fuente
                    clean = clean_title(title)
                    clean_link = escape_link(link)
                    source_lines.append(f"  [{clean}]({clean_link})")
                sub_lines.append("\n".join(source_lines))
                # Sin sleep por fuente: el rate-limit vive en fetch_all_rss (stagger).

            if sub_has_content:
                section_lines.append("\n".join(sub_lines))
                section_has_content = True

        if section_has_content:
            print("\n".join(section_lines))
            print("")
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
            footer_line += f" ({_stats.fail} fallos: {failed_list})"
        footer_line += "_\n"
        print(footer_line)
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
        logging.warning("Polymarket subprocess failed: %s", e)

    # Markets
    crypto = fetch_crypto()
    curr = fetch_currencies()
    if crypto or curr:
        print("**💰 MERCADOS**\n")
        for sym, price, change, emoji in crypto:
            print(f"• {emoji} {sym}: ${price:,.2f} ({change:+.2f}%)")
        for label, rate, note in curr:
            print(f"• {label}: ${rate:,.2f} ({note})")


if __name__ == "__main__":
    main()
