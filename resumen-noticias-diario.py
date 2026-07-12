#!/usr/bin/env python3
"""Diario Global Hermes — fuentes multiregión, multi-ideología."""

import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hermes_common import retry_request

# ═══════════════════════════════════════════
# FEEDS: región → subsección → [(nombre, url_rss), ...]
# ═══════════════════════════════════════════
FEEDS = [
    (
        "🌍 GEOPOLÍTICA & GLOBAL",
        [
            (
                "Mainstream / Wires",
                [
                    (
                        "Reuters",
                        "https://news.google.com/rss/search?q=site:reuters.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "AP",
                        "https://news.google.com/rss/search?q=site:apnews.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "Financial Times",
                        "https://news.google.com/rss/search?q=site:ft.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            ),
            (
                "Multipolar / Contrarian",
                [
                    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
                    (
                        "SCMP (HK/CN)",
                        "https://news.google.com/rss/search?q=site:scmp.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "ZeroHedge",
                        "https://news.google.com/rss/search?q=site:zerohedge.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            ),
        ],
    ),
    (
        "🇪🇺 EUROPA",
        [
            (
                "Pro-UE / Centrista",
                [
                    ("France 24 (🇫🇷)", "https://www.france24.com/en/rss"),
                    ("Le Monde EN (🇫🇷)", "https://www.lemonde.fr/en/rss/une.xml"),
                    ("DW (🇩🇪)", "https://rss.dw.com/rdf/rss-en-all"),
                    ("The Guardian (🇬🇧)", "https://www.theguardian.com/world/rss"),
                    ("BBC Mundo", "http://feeds.bbci.co.uk/mundo/rss.xml"),
                    ("Euronews", "https://www.euronews.com/rss"),
                ],
            ),
            (
                "Euroescéptica / Alt",
                [
                    ("RT", "https://actualidad.rt.com/rss"),
                ],
            ),
        ],
    ),
    (
        "🇺🇸 AMÉRICAS",
        [
            (
                "Mainstream US",
                [
                    (
                        "NYT",
                        "https://news.google.com/rss/search?q=site:nytimes.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "WaPo",
                        "https://news.google.com/rss/search?q=site:washingtonpost.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            ),
            (
                "Derecha / Conservador",
                [
                    ("Breitbart", "https://www.breitbart.com/feed/"),
                    (
                        "Fox News",
                        "https://news.google.com/rss/search?q=site:foxnews.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            ),
            (
                "Izquierda Radical",
                [
                    ("WSWS", "https://www.wsws.org/en/rss.xml"),
                ],
            ),
            (
                "Latinoamérica",
                [
                    (
                        "El País (🇪🇸)",
                        "https://news.google.com/rss/search?q=site:english.elpais.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            ),
        ],
    ),
    (
        "🇷🇺 RUSIA",
        [
            (
                "Estatal / Pro-Kremlin",
                [
                    ("RT EN", "https://www.rt.com/rss/"),
                    (
                        "Sputnik",
                        "https://news.google.com/rss/search?q=site:sputnikglobe.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            )
        ],
    ),
    (
        "🌏 ASIA-PACÍFICO",
        [
            (
                "Asia-Pacífico",
                [
                    (
                        "SCMP (🇭🇰)",
                        "https://news.google.com/rss/search?q=site:scmp.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "Nikkei Asia (🇯🇵)",
                        "https://news.google.com/rss/search?q=site:nikkei.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "NHK World (🇯🇵)",
                        "https://news.google.com/rss/search?q=site:nhk.or.jp+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                    (
                        "Times of India (🇮🇳)",
                        "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
                    ),
                    (
                        "Xinhua (🇨🇳)",
                        "https://news.google.com/rss/search?q=site:xinhuanet.com+when:24h&hl=en-US&gl=US&ceid=US:en",
                    ),
                ],
            )
        ],
    ),
    (
        "💻 TECNOLOGÍA",
        [
            (
                "Vanguardia",
                [
                    ("Hacker News", "https://hnrss.org/frontpage"),
                    ("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index"),
                    ("Xataka", "https://www.xataka.com/feed.xml"),
                ],
            )
        ],
    ),
    (
        "🇲🇽 MÉXICO",
        [
            (
                "Crítica / Mercados",
                [
                    (
                        "Reforma",
                        "https://news.google.com/rss/search?q=site:reforma.com+when:24h&hl=es-419&gl=MX&ceid=MX:es-419",
                    ),
                    ("El Financiero", "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/"),
                ],
            ),
            (
                "Oficialista",
                [
                    (
                        "La Jornada",
                        "https://news.google.com/rss/search?q=site:jornada.com.mx+when:24h&hl=es-419&gl=MX&ceid=MX:es-419",
                    ),
                    ("SinEmbargo", "https://www.sinembargo.mx/feed"),
                ],
            ),
            (
                "Local MTY",
                [
                    (
                        "El Norte",
                        "https://news.google.com/rss/search?q=site:elnorte.com+when:24h&hl=es-419&gl=MX&ceid=MX:es-419",
                    ),
                ],
            ),
        ],
    ),
    (
        "⚽ DEPORTES",
        [
            (
                "Liga MX / Rayados",
                [
                    (
                        "MedioTiempo",
                        "https://news.google.com/rss/search?q=site:mediotiempo.com+Rayados+when:24h&hl=es-419&gl=MX&ceid=MX:es-419",
                    ),
                    (
                        "ESPN",
                        "https://news.google.com/rss/search?q=site:espn.com.mx+Rayados+when:24h&hl=es-419&gl=MX&ceid=MX:es-419",
                    ),
                ],
            )
        ],
    ),
]


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


def clean_title(title):
    """Limpia título: remueve source suffix, escapa caracteres."""
    # Remove " - SourceName" suffix
    title = title.split(" - ")[0].strip()
    # Replace brackets that break markdown
    title = title.replace("[", "(").replace("]", ")")
    return title


def escape_link(link):
    """Normaliza URLs de Google News: quita tracking params y protege caracteres especiales."""
    link = re.sub(r"[?&]oc=\d+", "", link)
    link = re.sub(r"[?&]utm_[^&]+", "", link)
    link = re.sub(r"[?&]ceid=[^&]+", "", link)
    # Si queda solo '?' al final, quitarlo
    link = re.sub(r"[?&]$", "", link)
    # Proteger ) en URLs (rompe Markdown [text](url))
    link = link.replace(")", "%29")
    return link


# Cache global para URLs acortadas (evita llamadas repetidas a TinyURL)
_URL_CACHE = {}


def shorten_url(long_url, timeout=5):
    """Acorta URL con TinyURL (gratis, sin API key). Cachea resultados."""
    if "news.google.com" not in long_url:
        return long_url
    if long_url in _URL_CACHE:
        return _URL_CACHE[long_url]
    try:
        r = requests.get(
            "https://tinyurl.com/api-create.php", params={"url": long_url}, timeout=timeout
        )
        if r.status_code == 200 and r.text.startswith("http"):
            short = r.text.strip()
            _URL_CACHE[long_url] = short
            return short
    except Exception:
        pass
    return long_url


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

            for source_name, url in sources:
                items = fetch_rss(url, source_name)
                if not items:
                    continue

                if not sub_has_content:
                    sub_lines.append(f"_{sub_name}_")
                    sub_has_content = True
                source_lines = [f"• *{source_name}*"]
                for title, link in items[:1]:  # 1 item por fuente
                    clean = clean_title(title)
                    clean_link = escape_link(link)
                    short_link = shorten_url(clean_link)
                    source_lines.append(f"  [{clean}]({short_link})")
                sub_lines.append("\n".join(source_lines))
                time.sleep(0.8)

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

    # Polymarket predictions
    try:
        polymarket_script = os.path.join(os.path.dirname(__file__), "polymarket-diario.py")
        subprocess.run([sys.executable, polymarket_script], timeout=25)
    except Exception:
        pass  # Silent fail — no bloquea el reporte

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
