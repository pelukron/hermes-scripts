#!/usr/bin/env python3
"""gate-audit.py — CLI de la matriz de gates por repo.

Uso::

    uv run python bin/gate-audit.py --markdown   # matriz a stdout + out/gate-audit.md
    uv run python bin/gate-audit.py --digest     # digest Telegram a stdout + out/gate-audit.md

Requiere `gh` autenticado (lectura). Sin auto-issues ni escrituras en otros repos.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.gate_audit import (  # noqa: E402
    BACKLOG_REPOS,
    DEFAULT_OWNER,
    collect,
    render_digest,
    render_markdown,
    summarize,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Argumentos del CLI."""
    parser = argparse.ArgumentParser(description="Matriz de gates por repo.")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="owner de GitHub")
    parser.add_argument("--repos", nargs="*", default=BACKLOG_REPOS, help="repos a auditar")
    parser.add_argument("--markdown", action="store_true", help="imprime la matriz (default)")
    parser.add_argument("--digest", action="store_true", help="imprime el digest compacto")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="modo job semanal: silencioso si verde (rc 0 sin salida); "
        "con huecos imprime el digest y sale rc 1, como adopted-sha-audit",
    )
    parser.add_argument("--out", default="out/gate-audit.md", help="archivo del reporte")
    parser.add_argument("--date", default=str(date.today()), help="fecha del digest")
    parser.add_argument("--no-write", action="store_true", help="no escribe el archivo")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Colecta, renderiza, escribe `out/gate-audit.md` e imprime."""
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):  # consolas Windows (cp1252)
            reconfigure(encoding="utf-8")
    except ValueError:
        pass
    args = parse_args(argv)
    records = collect(args.owner, args.repos)
    summary = summarize(records)
    out_path = REPO / args.out
    if not args.no_write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(records, summary), encoding="utf-8")
    if args.digest:
        if args.quiet and not summary["with_gaps"]:
            return 0
        print(render_digest(records, summary, args.date))
        return 1 if args.quiet and summary["with_gaps"] else 0
    print(render_markdown(records, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
