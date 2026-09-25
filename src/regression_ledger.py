"""regression-ledger — cola deduplicada de anomalías nocturnas (#266).

Lo llaman canary, adopted-sha-audit y cron-doctor-daily al terminar. Un solo seam.

Ledger en ``$HERMES_HOME/regression-anomalies.json`` (vía ``state_dir()``), una fila
por firma. Firma = job + paso + tipo + detalle normalizado (sin rutas absolutas,
sin SHA, sin timestamps, sin números de línea).

Reglas cerradas del issue:

- ``codigo`` o ``huella`` la primera vez: ``gh issue create``, título
  ``regression: <firma corta>``, cuerpo con la muestra, el SHA adoptado,
  ``bash bin/gate.sh`` y el job que lo vio. Label ``🐛 bug``. Guarda el número.
- Misma firma con el issue abierto: solo sube ``count`` y ``last_seen``.
- Firma que vuelve con el issue cerrado: issue nuevo que cita el anterior.
- ``entorno``: se anota y no abre ticket. A la tercera noche seguida sí abre.
- Sin ``gh`` o sin token el ledger se escribe igual y la noche siguiente reintenta.
- ``no_agent``, cero tokens. Telegram no cambia: el issue es la cola.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Callable

from hermes_common import gh_bin, state_dir

LEDGER_NAME = "regression-anomalies.json"
ISSUE_LABEL = "🐛 bug"
ENVIRONMENT_THRESHOLD = 3

_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_ABS_RE = re.compile(r"/[^\s:'\"]+")
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?([^\s]*)?")
_LINE_RE = re.compile(r"(:)\d{1,5}\b")
_HOME_RE = re.compile(r"/home/[^\s:'\"]+|C:[\\\/][^\s:'\"]+|~(/[^\s:'\"]*)?")


def normalize_detail(detail: str) -> str:
    """Detalle sin partes que cambian cada noche (rutas, SHA, tiempos, líneas)."""
    text = detail or ""
    text = _HOME_RE.sub("<path>", text)
    text = _ABS_RE.sub("<path>", text)
    text = _SHA_RE.sub("<sha>", text)
    text = _TS_RE.sub("<ts>", text)
    text = _LINE_RE.sub(r"\1<n>", text)
    return " ".join(text.split())[:200]


def signature(job: str, step: str, kind: str, detail: str) -> str:
    """Clave estable de dedup: job + paso + tipo + detalle normalizado."""
    return f"{job}|{step}|{kind}|{normalize_detail(detail)}"


def short_signature(key: str) -> str:
    """Firma corta para el título del issue (una línea, sin ruido)."""
    return " ".join(key.split("|"))[:80]


def ledger_path(home: Path | None = None) -> Path:
    """Ruta del ledger bajo el estado del runtime."""
    base = home if home is not None else state_dir()
    return Path(base) / LEDGER_NAME


def load_ledger(path: Path) -> dict[str, dict[str, Any]]:
    """Ledger como dict firma -> fila. Archivo ausente o roto = ledger vacío."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    if isinstance(data, list):
        rows: dict[str, dict[str, Any]] = {}
        for row in data:
            if isinstance(row, dict) and row.get("signature"):
                rows[str(row["signature"])] = row
        return rows
    return {}


def save_ledger(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    """Escribe el ledger aunque no haya ``gh`` (la noche siguiente reintenta)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


RunGh = Callable[..., subprocess.CompletedProcess]


def _gh(args: list[str], run: RunGh | None = None) -> subprocess.CompletedProcess:
    runner = run or subprocess.run
    return runner(
        [gh_bin(), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def issue_is_open(number: int, run: RunGh | None = None) -> bool | None:
    """True si el issue sigue abierto, False si cerrado, None si no se pudo saber."""
    try:
        proc = _gh(["issue", "view", str(number), "--json", "state"], run=run)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return bool(json.loads(proc.stdout or "{}").get("state") == "OPEN")
    except json.JSONDecodeError:
        return None


def create_issue(
    job: str,
    key: str,
    sample: str,
    sha: str,
    reopened_from: int | None = None,
    run: RunGh | None = None,
) -> int | None:
    """Crea ``regression: <firma corta>``. None si no hay gh/token (reintenta mañana)."""
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        return None
    body = (
        f"Job: {job}\n"
        f"Firma: {key}\n"
        f"Muestra: {sample}\n"
        f"SHA adoptado: {sha}\n"
        "Repro: bash bin/gate.sh\n"
    )
    if reopened_from:
        body += f"\nVuelve tras cerrar #{reopened_from}.\n"
    try:
        proc = _gh(
            [
                "issue",
                "create",
                "--title",
                f"regression: {short_signature(key)}",
                "--body",
                body,
                "--label",
                ISSUE_LABEL,
            ],
            run=run,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or "") + (proc.stderr or "")
    match = re.search(r"/issues/(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"#(\d+)", text)
    return int(match.group(1)) if match else None


def _today() -> str:
    return date.today().isoformat()


def record(
    job: str,
    step: str,
    kind: str,
    detail: str,
    sha: str,
    home: Path | None = None,
    run: RunGh | None = None,
    today: str | None = None,
) -> dict[str, Any]:
    """Registra una anomalía y abre ticket solo cuando toca. Nunca lanza por gh."""
    key = signature(job, step, kind, detail)
    path = ledger_path(home)
    rows = load_ledger(path)
    day = today or _today()
    row = rows.get(key, {})
    sample = (detail or "")[:200]

    if row:
        row["last_seen"] = day
        row["count"] = int(row.get("count", 0)) + 1
        row["last_sha"] = sha
        row.setdefault("sample", sample)
    else:
        row = {
            "signature": key,
            "first_seen": day,
            "last_seen": day,
            "count": 1,
            "last_sha": sha,
            "sample": sample,
            "issue": None,
            "environment_streak": 0,
        }

    issue_number = row.get("issue")
    if kind == "entorno":
        streak = int(row.get("environment_streak", 0)) + 1
        row["environment_streak"] = streak
        if streak >= ENVIRONMENT_THRESHOLD and not issue_number:
            new_issue = create_issue(job, key, sample, sha, run=run)
            if new_issue:
                row["issue"] = new_issue
        elif issue_number:
            is_open = issue_is_open(int(issue_number), run=run)
            if is_open is False:
                new_issue = create_issue(
                    job, key, sample, sha, reopened_from=int(issue_number), run=run
                )
                if new_issue:
                    row["issue"] = new_issue
        rows[key] = row
        save_ledger(path, rows)
        return row

    if issue_number:
        is_open = issue_is_open(int(issue_number), run=run)
        if is_open is False:
            new_issue = create_issue(
                job, key, sample, sha, reopened_from=int(issue_number), run=run
            )
            if new_issue:
                row["issue"] = new_issue
        rows[key] = row
        save_ledger(path, rows)
        return row

    new_issue = create_issue(job, key, sample, sha, run=run)
    if new_issue:
        row["issue"] = new_issue
    rows[key] = row
    save_ledger(path, rows)
    return row


def record_batch(
    job: str,
    sha: str,
    failures: list[dict[str, str]],
    home: Path | None = None,
    run: RunGh | None = None,
) -> list[dict[str, Any]]:
    """Un solo seam para los tres jobs. Un fallo del ledger no rompe la noche."""
    rows: list[dict[str, Any]] = []
    for failure in failures or []:
        try:
            rows.append(
                record(
                    job,
                    str(failure.get("paso", "")),
                    str(failure.get("tipo", "")),
                    str(failure.get("detalle", "")),
                    sha,
                    home=home,
                    run=run,
                )
            )
        except Exception:
            continue
    return rows
