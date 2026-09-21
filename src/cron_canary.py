"""cron-canary — suite sintética nocturna de entrypoints (#218).

Corre la allow-list con ``HERMES_HOME`` temporal, afirma que el estado real
no cambió, y (si hay token) manda un payload de 1 mensaje a Telegram.
Silencioso si todo está verde. ``no_agent``, 0 tokens.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from hermes_common import report_failure, state_dir

# Mutan de verdad: tarball, borrados, clones. Su validación es el drift-check.
DENY_LIST = {
    "backup-diario": "muta tarball de ~/.hermes",
    "cleanup-housekeeping": "borra backups y caches",
    "sync-runtime": "git merge --ff-only en clones reales",
    "runtime-sync": "git merge --ff-only en clones reales",
}

# Herméticos desde #215 (state_dir). Incluye monitor-ram-mexico.
ALLOW_LIST = (
    "resumen-noticias-diario",
    "resumen-rayados-diario",
    "resumen-tigres-diario",
    "polymarket-diario",
    "reporte-uso-hermes",
    "monitor-ram-mexico",
)

STEP_TIMEOUT = 300
TELEGRAM_UTF16_LIMIT = 4096
CANARY_TEXT = "cron-canary ok"


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def fingerprint(root: Path) -> str:
    """Huella del estado: archivos bajo root, menos logs/ y los sidecars de SQLite.

    Los `-shm`/`-wal` de una DB viva aparecen y desaparecen mientras Hermes la usa: no son
    estado, y contarlos dejaría la huella inestable. Y un archivo que se esfuma entre listarlo
    y leerlo tampoco puede romper la corrida (#241).
    """
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if "logs" in path.parts or path.name.endswith(("-shm", "-wal")):
            continue
        try:
            datos = path.read_bytes()
        except FileNotFoundError:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(datos)
    return digest.hexdigest()


def canary_payload() -> str:
    text = CANARY_TEXT
    if utf16_len(text) > TELEGRAM_UTF16_LIMIT:
        raise ValueError("payload canary excede 1 mensaje")
    return text


def run_drift_check(repo: Path, hermes_home: Path) -> str | None:
    """None si sin drift. Texto del fallo si no."""
    proc = subprocess.run(
        [sys.executable, str(repo / "src" / "install_cron.py"), "--check", "--quiet"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        env={**os.environ, "HERMES_HOME": str(hermes_home)},
    )
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "drift-check rc!=0").strip()
    return None


def run_entrypoint(name: str, repo: Path, sandbox: Path) -> str | None:
    """None si rc=0. Nombre del fallo si no."""
    env = {**os.environ, "HERMES_HOME": str(sandbox)}
    proc = subprocess.run(
        ["uv", "run", name],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        env=env,
    )
    if proc.returncode != 0:
        return f"{name} rc={proc.returncode}"
    return None


def send_canary(text: str, post=None) -> str | None:
    """None si entregó (message_id) o no hay token. Texto de fallo si no."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text}
    if post is None:
        import requests

        def post(u, data):
            return requests.post(u, json=data, timeout=20).json()

    body = post(url, payload)
    if not body.get("ok") or not (body.get("result") or {}).get("message_id"):
        return f"canary send failed: {body!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    """0 y stdout vacío si sano. 1 y el paso rojo si no."""
    del argv  # CLI sin flags: el cron no pasa nada.
    repo = Path(__file__).resolve().parent.parent
    real = state_dir()
    before = fingerprint(real)
    failed: str | None = None

    failed = run_drift_check(repo, real)
    if not failed:
        with tempfile.TemporaryDirectory(prefix="cron-canary-") as tmp:
            sandbox = Path(tmp)
            for name in ALLOW_LIST:
                failed = run_entrypoint(name, repo, sandbox)
                if failed:
                    break
    if not failed:
        after = fingerprint(real)
        if before != after:
            failed = "estado real mutó (huella distinta)"
    if not failed:
        failed = send_canary(canary_payload())

    if failed:
        print(f"cron-canary: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(report_failure(exc))
