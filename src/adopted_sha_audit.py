"""adopted-sha-audit — e2e nocturno del sha que sync-runtime adoptó (#235).

Corre el gate sobre el árbol desplegado (después de runtime-sync 04:25),
deja una línea de historia por noche y calla si está verde.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Callable

import defusedxml.ElementTree as ET  # noqa: N817

from healthcheck import load_ping_url, ping
from hermes_common import report_failure, state_dir

HISTORY_NAME = "adopted-sha-history.json"
STEP_TIMEOUT = 600
SCHEDULE = "0 5 * * *"

# El gate es **un** comando (#265): el mismo de local y CI. Las excepciones de
# pip-audit (#287) y el shellcheck viven en el Makefile, donde se juzga el riesgo;
# aquí ya no hay una tercera copia de la lista de pasos que pueda discrepar.
GATE_COMMAND = ("bash", "bin/gate.sh")

# Palabras que el spike midió como rojo de entorno, no de código.
_ENTORNO_MARKERS = (
    "ConnectionRefusedError",
    "Network is unreachable",
    "Temporary failure in name resolution",
    "Failed to establish a new connection",
    "hermes/cache/scratch",
    "No space left on device",
)

RunStep = Callable[[str, list[str], Path, dict[str, str]], subprocess.CompletedProcess]


def adopted_sha(repo: Path) -> str:
    """SHA completo de HEAD en el árbol desplegado."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (proc.stdout or "").strip()


def gate_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """TMPDIR saneado y sin VIRTUAL_ENV (trampas 1 y 2 del spike)."""
    env = dict(base if base is not None else os.environ)
    env.pop("VIRTUAL_ENV", None)
    # B108 no aplica: aquí no se crea ningún temporal, sólo se apunta TMPDIR a /tmp.
    tmp = "/tmp" if Path("/tmp").is_dir() else tempfile.gettempdir()  # nosec B108
    env["TMPDIR"] = tmp
    env["TEMP"] = tmp
    env["TMP"] = tmp
    return env


def classify(paso: str, output: str) -> str:
    """`codigo` vs `entorno`. pip-audit sin red y TMPDIR heredado son entorno.

    `paso` se conserva por compatibilidad de firma: con un solo comando (#265) no
    distingue la causa, la distingue el texto.
    """
    del paso
    blob = output or ""
    if any(marker in blob for marker in _ENTORNO_MARKERS):
        return "entorno"
    if "pip-audit" in blob.lower() and "error" in blob.lower():
        if "Connection" in blob or "timeout" in blob.lower() or "Max retries" in blob:
            return "entorno"
    return "codigo"


def parse_junit(path: Path) -> list[dict[str, str]]:
    """Fallos de pytest desde JUnit XML nativo. Sin dependencias nuevas."""
    if not path.is_file():
        return []
    root = ET.parse(path).getroot()
    fallos: list[dict[str, str]] = []
    for case in root.iter("testcase"):
        nodo = case.find("failure")
        if nodo is None:
            nodo = case.find("error")
        if nodo is None:
            continue
        nombre = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
        detalle = (nodo.get("message") or "").strip() or (nodo.text or "").strip()
        detalle = " ".join(detalle.split())[:200]
        tipo = classify("test", detalle + " " + (nodo.text or ""))
        fallos.append({"paso": "test", "tipo": tipo, "detalle": nombre or detalle})
    return fallos


def append_history(path: Path, record: dict[str, Any]) -> None:
    """Una línea por noche, verde o roja."""
    records: list[Any] = []
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = []
        if isinstance(loaded, list):
            records = loaded
    records.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(record: dict[str, Any]) -> str:
    """Un mensaje. Silencio es no llamarlo."""
    sha = str(record.get("sha_adoptado") or "")[:12]
    lines = [f"adopted-sha-audit: {record.get('veredicto')} sha={sha}"]
    for fallo in record.get("fallos") or []:
        lines.append(f"- {fallo.get('paso')} [{fallo.get('tipo')}]: {fallo.get('detalle')}")
    return "\n".join(lines)


def _default_run(
    paso: str, argv: list[str], repo: Path, env: dict[str, str]
) -> subprocess.CompletedProcess:
    del paso
    return subprocess.run(
        argv,
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        env=env,
    )


def run_gate(
    repo: Path,
    env: dict[str, str],
    junit: Path,
    run: RunStep | None = None,
) -> list[dict[str, str]]:
    """El gate entero en un comando (#265). Un rojo entra clasificado.

    `GATE_JUNIT` viaja en el entorno: el Makefile escribe ahí el XML de pytest, que es
    la única parte del gate con detalle por prueba. Si el rojo no es de tests (lint,
    shellcheck, mypy, bandit, pip-audit) no hay XML y se reporta el comando con su
    salida clasificada.
    """
    runner = run or _default_run
    env = {**env, "GATE_JUNIT": str(junit)}
    proc = runner("gate", list(GATE_COMMAND), repo, env)
    if proc.returncode == 0:
        return []
    output = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    parsed = parse_junit(junit)
    if parsed:
        return parsed
    return [
        {
            "paso": "gate",
            "tipo": classify("gate", output),
            "detalle": (proc.stderr or proc.stdout or f"rc={proc.returncode}").strip()[:200],
        }
    ]


def main(argv: list[str] | None = None, run: RunStep | None = None) -> int:
    """0 y stdout vacío si verde. 1 y un mensaje si hay fallos. Siempre escribe historia.

    Ping ``/start`` al arrancar y success/``/fail`` al terminar (#236). Si la
    caja muere a mitad, el testigo externo alerta: no hay silencio.
    """
    del argv
    url = load_ping_url()
    ping(url, "start")
    try:
        rc = _audit(run)
    except Exception:
        ping(url, "fail")
        raise
    ping(url, "fail" if rc else "")
    return rc


def _audit(run: RunStep | None = None) -> int:
    repo = Path(__file__).resolve().parent.parent
    home = state_dir()
    sha = adopted_sha(repo)
    env = gate_env()
    junit_fh = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
    junit = Path(junit_fh.name)
    junit_fh.close()
    try:
        fallos = run_gate(repo, env, junit, run=run)
    finally:
        junit.unlink(missing_ok=True)
    record = {
        "fecha": date.today().isoformat(),
        "sha_adoptado": sha,
        "veredicto": "rojo" if fallos else "verde",
        "fallos": fallos,
        "entorno": {"tmpdir": env.get("TMPDIR", ""), "python": sys.executable},
    }
    append_history(home / HISTORY_NAME, record)
    if fallos:
        print(digest(record))
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(report_failure(exc))
