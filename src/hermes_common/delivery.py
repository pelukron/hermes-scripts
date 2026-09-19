"""Contratos de entrega a Telegram: presupuesto UTF-16 y markdown de links (#216)."""

from __future__ import annotations

import math
import re

# Tope duro del sender de Telegram. Medido 2026-09-18: 2 chunks parten un
# enlace y el markdown de ese chunk cae a texto plano. El contrato es 1 mensaje.
TELEGRAM_UTF16_LIMIT = 4096

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")


def utf16_len(text: str) -> int:
    """Unidades UTF-16 del texto (el corte de Telegram no es en code points)."""
    return len(text.encode("utf-16-le")) // 2


def telegram_chunks(text: str, limit: int = TELEGRAM_UTF16_LIMIT) -> int:
    """Cuántos mensajes mandaría Telegram al cortar de ``limit`` en ``limit``."""
    n = utf16_len(text)
    if n <= 0:
        return 0
    return math.ceil(n / limit)


def markdown_v2_link_issues(text: str) -> list[str]:
    """Problemas en ``[titulo](url)`` que tumban MarkdownV2.

    El disparador medido son paréntesis sin escapar en el título. ``.`` y ``-``
    en el título se listan: no rompen el parseo del enlace, pero MarkdownV2 los
    reserva — el presupuesto de 1 mensaje evita el corte a mitad de URL.
    """
    issues: list[str] = []
    for title, url in _LINK_RE.findall(text):
        if "(" in title or ")" in title:
            issues.append(f"titulo con parentesis: {title!r}")
        if ")" in url:
            issues.append(f"url con parentesis: {url!r}")
    return issues
