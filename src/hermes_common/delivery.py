"""Contratos de entrega a Telegram: presupuesto UTF-16 y markdown de links (#216)."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# Tope duro del sender de Telegram. Medido 2026-09-18: 2 chunks parten un
# enlace y el markdown de ese chunk cae a texto plano. El contrato es 1 mensaje.
TELEGRAM_UTF16_LIMIT = 4096

# ADR 0005: el presupuesto es por mensaje, no por corrida. `LINE_BUDGET` es el que hace segura la
# entrega multi-mensaje: mientras ninguna línea lo pase, el chunker de Hermes corta en un '\n' y
# ningún enlace se parte. `REPORT_BUDGET` es lo que un reporte puede gastar en total (~2 mensajes).
LINE_BUDGET = 3800
REPORT_BUDGET = 7100

# Separador y pausa entre bloques: viven aquí para que todas las áreas fragmenten igual (el gateway
# manda cada bloque como su propio mensaje).
BLOCK_SEPARATOR = "\n---\n"
BLOCK_PAUSE_SECONDS = 1.5

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


@dataclass(frozen=True)
class DeliveryResult:
    """One block fitted to a single message, plus what the budget left out."""

    text: str
    dropped: int
    chunks: int


def _note(dropped: int) -> str:
    """The line declaring what the budget left out."""
    return f"… +{dropped} fuera"


def _join(lines: list[str], dropped: int) -> str:
    """The block as it will be delivered: the kept lines plus, if any, the note."""
    body = "\n".join(lines)
    if not dropped:
        return body
    note = _note(dropped)
    return f"{body}\n{note}" if body else note


def prepare(
    blocks: Iterable[str],
    *,
    message_budget: int = TELEGRAM_UTF16_LIMIT,
    line_budget: int = LINE_BUDGET,
) -> list[DeliveryResult]:
    """Fit each block to ONE message, cutting on whole lines only.

    ``message_budget`` is the per-message budget: an area may declare a tighter one than the
    sender's hard limit (ADR 0009, one area one policy), and it is clamped to
    ``TELEGRAM_UTF16_LIMIT`` because no budget talks the sender into splitting a link.
    A line longer than ``line_budget`` is never cut: it is dropped whole and counted, because a cut
    inside a URL reaches the chat as plain text with the URL exposed (#278, ADR 0005). Whatever the
    budget left out is declared in the block itself (``+N fuera``), so no silent truncation ships.
    A block carrying no content is not delivered at all: empty stdout means no message.
    """
    cap = min(message_budget, TELEGRAM_UTF16_LIMIT)
    results: list[DeliveryResult] = []
    for block in blocks:
        if not block or not block.strip():
            continue
        kept: list[str] = []
        dropped = 0
        for line in block.splitlines():
            if line.strip() and utf16_len(line) > line_budget:
                dropped += 1
                continue
            kept.append(line)
        while kept and utf16_len(_join(kept, dropped)) > cap:
            kept.pop()
            dropped += 1
        text = _join(kept, dropped)
        results.append(DeliveryResult(text=text, dropped=dropped, chunks=telegram_chunks(text)))
    return results


def emit(
    blocks: Iterable[str],
    *,
    write: Callable[[str], None],
    message_budget: int = TELEGRAM_UTF16_LIMIT,
    line_budget: int = LINE_BUDGET,
) -> list[DeliveryResult]:
    """Write each block as its own message, then pause before the next one.

    ``write`` is the caller's sink — the report scripts pass ``log.info`` — so this module never
    decides logging. The separator and the pause are declared here, once, for every area.
    """
    results = prepare(blocks, message_budget=message_budget, line_budget=line_budget)
    for result in results:
        write(result.text)
        write(BLOCK_SEPARATOR)
        time.sleep(BLOCK_PAUSE_SECONDS)
    return results
