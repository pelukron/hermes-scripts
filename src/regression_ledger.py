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
ENTORNO_UMBRAL = 3

_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_ABS_RE = re.compile(r"/[^\s:'\"]+")
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?([^\s]*)?")
_LINE_RE = re.compile(r"(:)\d{1,5}\b")
_HOME_RE = re.compile(r"/home/[^\s:'\"]+|C:[\\\/][^\s:'\"]+|~(/[^\s:'\"]*)?")


def normalize_detail(detalle: str) -> str:
    """Detalle sin partes que cambian cada noche (rutas, SHA, tiempos, líneas)."""
    texto = detalle or ""
    texto = _HOME_RE.sub("<path>", texto)
    texto = _ABS_RE.sub("<path>", texto)
    texto = _SHA_RE.sub("<sha>", texto)
    texto = _TS_RE.sub("<ts>", texto)
    texto = _LINE_RE.sub(r"\1<n>", texto)
    return " ".join(texto.split())[:200]


def signature(job: str, paso: str, tipo: str, detalle: str) -> str:
    """Clave estable de dedup: job + paso + tipo + detalle normalizado."""
    return f"{job}|{paso}|{tipo}|{normalize_detail(detalle)}"


def short_signature(firma: str) -> str:
    """Firma corta para el título del issue (una línea, sin ruido)."""
    return " ".join(firma.split("|"))[:80]


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
        filas: dict[str, dict[str, Any]] = {}
        for fila in data:
            if isinstance(fila, dict) and fila.get("firma"):
                filas[str(fila["firma"])] = fila
        return filas
    return {}


def save_ledger(path: Path, filas: dict[str, dict[str, Any]]) -> None:
    """Escribe el ledger aunque no haya ``gh`` (la noche siguiente reintenta)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(filas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


RunGh = Callable[..., subprocess.CompletedProcess]


def _gh(args: list[str], run: RunGh | None = None) -> subprocess.CompletedProcess:
    runner = run or subprocess.run
    return runner(
        [gh_bin(), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def issue_is_open(numero: int, run: RunGh | None = None) -> bool | None:
    """True si el issue sigue abierto, False si cerrado, None si no se pudo saber."""
    try:
        proc = _gh(["issue", "view", str(numero), "--json", "state"], run=run)
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
    firma: str,
    muestra: str,
    sha: str,
    cita: int | None = None,
    run: RunGh | None = None,
) -> int | None:
    """Crea ``regression: <firma corta>``. None si no hay gh/token (reintenta mañana)."""
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        return None
    cuerpo = (
        f"Job: {job}\n"
        f"Firma: {firma}\n"
        f"Muestra: {muestra}\n"
        f"SHA adoptado: {sha}\n"
        "Repro: bash bin/gate.sh\n"
    )
    if cita:
        cuerpo += f"\nVuelve tras cerrar #{cita}.\n"
    try:
        proc = _gh(
            [
                "issue",
                "create",
                "--title",
                f"regression: {short_signature(firma)}",
                "--body",
                cuerpo,
                "--label",
                ISSUE_LABEL,
            ],
            run=run,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    texto = (proc.stdout or "") + (proc.stderr or "")
    match = re.search(r"/issues/(\d+)", texto)
    if match:
        return int(match.group(1))
    match = re.search(r"#(\d+)", texto)
    return int(match.group(1)) if match else None


def _hoy() -> str:
    return date.today().isoformat()


def record(
    job: str,
    paso: str,
    tipo: str,
    detalle: str,
    sha: str,
    home: Path | None = None,
    run: RunGh | None = None,
    hoy: str | None = None,
) -> dict[str, Any]:
    """Registra una anomalía y abre ticket solo cuando toca. Nunca lanza por gh."""
    firma = signature(job, paso, tipo, detalle)
    path = ledger_path(home)
    filas = load_ledger(path)
    dia = hoy or _hoy()
    fila = filas.get(firma, {})
    muestra = (detalle or "")[:200]

    if fila:
        fila["last_seen"] = dia
        fila["count"] = int(fila.get("count", 0)) + 1
        fila["last_sha"] = sha
        fila.setdefault("muestra", muestra)
    else:
        fila = {
            "firma": firma,
            "first_seen": dia,
            "last_seen": dia,
            "count": 1,
            "last_sha": sha,
            "muestra": muestra,
            "issue": None,
            "entorno_streak": 0,
        }

    numero = fila.get("issue")
    if tipo == "entorno":
        racha = int(fila.get("entorno_streak", 0)) + 1
        fila["entorno_streak"] = racha
        if racha >= ENTORNO_UMBRAL and not numero:
            nuevo = create_issue(job, firma, muestra, sha, run=run)
            if nuevo:
                fila["issue"] = nuevo
        elif numero:
            abierto = issue_is_open(int(numero), run=run)
            if abierto is False:
                nuevo = create_issue(job, firma, muestra, sha, cita=int(numero), run=run)
                if nuevo:
                    fila["issue"] = nuevo
        filas[firma] = fila
        save_ledger(path, filas)
        return fila

    if numero:
        abierto = issue_is_open(int(numero), run=run)
        if abierto is False:
            nuevo = create_issue(job, firma, muestra, sha, cita=int(numero), run=run)
            if nuevo:
                fila["issue"] = nuevo
        filas[firma] = fila
        save_ledger(path, filas)
        return fila

    nuevo = create_issue(job, firma, muestra, sha, run=run)
    if nuevo:
        fila["issue"] = nuevo
    filas[firma] = fila
    save_ledger(path, filas)
    return fila


def record_batch(
    job: str,
    sha: str,
    fallos: list[dict[str, str]],
    home: Path | None = None,
    run: RunGh | None = None,
) -> list[dict[str, Any]]:
    """Un solo seam para los tres jobs. Un fallo del ledger no rompe la noche."""
    filas: list[dict[str, Any]] = []
    for fallo in fallos or []:
        try:
            filas.append(
                record(
                    job,
                    str(fallo.get("paso", "")),
                    str(fallo.get("tipo", "")),
                    str(fallo.get("detalle", "")),
                    sha,
                    home=home,
                    run=run,
                )
            )
        except Exception:
            continue
    return filas
