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
    reserva. También lista las líneas con corchetes o paréntesis sin cerrar: un
    corte a mitad de URL emite `[titular](https://…` y Telegram lo entrega como
    texto plano, con la URL cruda a la vista (#278: 4 de 10 enlaces así).
    """
    issues: list[str] = []
    for title, url in _LINK_RE.findall(text):
        if "(" in title or ")" in title:
            issues.append(f"titulo con parentesis: {title!r}")
        if ")" in url:
            issues.append(f"url con parentesis: {url!r}")
    # El regex de arriba sólo ve enlaces CERRADOS, así que era ciego justo al defecto que se
    # entregaba a diario. Las URLs ya vienen con `)` escapado a `%29` (news_utils.clean_url),
    # así que el conteo por línea es un contrato válido.
    for n, linea in enumerate(text.splitlines(), 1):
        if linea.count("[") != linea.count("]"):
            issues.append(f"linea {n}: corchetes sin cerrar: {linea[:60]!r}")
        elif linea.count("(") != linea.count(")"):
            issues.append(f"linea {n}: parentesis sin cerrar: {linea[:60]!r}")
    return issues
