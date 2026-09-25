"""cron-canary — suite sintética nocturna de entrypoints (#218).

Corre la allow-list con ``HERMES_HOME`` temporal, afirma que lo que los jobs
poseen no cambió, y (si hay token) manda un payload de 1 mensaje a Telegram.
Silencioso si todo está verde. ``no_agent``, 0 tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from hermes_common import report_failure, state_dir, uv_bin

try:
    from src import regression_ledger as _ledger
except ImportError:  # pragma: no cover
    import regression_ledger as _ledger  # type: ignore[no-redef]

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


# Libro que Hermes reescribe al guardar o al cerrar una corrida (cron/jobs.py:
# save_jobs sella updated_at; mark_job_run sella estado, claims y repeat.completed).
# No es la definición del job. #258
_CLAVES_DE_LATIDO = frozenset(
    {
        "updated_at",
        "last_run_at",
        "next_run_at",
        "last_status",
        "last_error",
        "last_delivery_error",
        "last_delivery_unverified",
        "failure_streak",
        "fire_claim",
        "run_claim",
        "pending_slot",
        "last_fire_error",
        "state",
        "completed",
        "manual_run_at",
        "manual_run_prompt",
    }
)


def _sin_latido(node: Any) -> Any:
    """Quita el libro de runtime: el ticker lo reescribe aunque el job no cambie (#258)."""
    if isinstance(node, dict):
        return {
            clave: _sin_latido(valor)
            for clave, valor in node.items()
            if clave not in _CLAVES_DE_LATIDO
        }
    if isinstance(node, list):
        return [_sin_latido(valor) for valor in node]
    return node


def _bytes_manifiesto(path: Path) -> bytes:
    """Manifiesto canónico. Si no es JSON, los bytes crudos: una corrupción también muta."""
    crudo = path.read_bytes()
    try:
        data = json.loads(crudo)
    except json.JSONDecodeError:
        return crudo
    return json.dumps(_sin_latido(data), sort_keys=True, separators=(",", ":")).encode()


def _clave_de(path: Path, root: Path) -> bytes:
    """Ruta que entra en la huella: relativa a root, o absoluta si el enlace vive fuera."""
    try:
        return path.relative_to(root).as_posix().encode()
    except ValueError:
        return path.as_posix().encode()


def _pieza(path: Path, root: Path, datos: bytes) -> tuple[bytes, bytes]:
    return _clave_de(path, root), datos


def _pieza_manifiesto(path: Path, root: Path) -> tuple[bytes, bytes] | None:
    try:
        return _pieza(path, root, _bytes_manifiesto(path))
    except FileNotFoundError:
        return None


def _pieza_archivo(path: Path, root: Path) -> tuple[bytes, bytes] | None:
    try:
        return _pieza(path, root, path.read_bytes())
    except FileNotFoundError:
        return None


def _leer_enlace(path: Path, root: Path) -> tuple[bytes, bytes]:
    """Identidad del enlace, no el cuerpo del skill: ese vive en el clon y lo mueve runtime-sync."""
    clave = _clave_de(path, root)
    try:
        if path.is_symlink():
            return clave, os.readlink(path).encode()
        if path.is_file():
            return clave, path.read_bytes()
    except (FileNotFoundError, OSError):
        return clave, b"absent"
    return clave, b"absent"


def _enlaces_declarados(root: Path) -> list[Path]:
    """Symlinks de config/runtime-clones.json, reubicados bajo ``root``."""
    config = Path(__file__).resolve().parent.parent / "config" / "runtime-clones.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    hogar = Path.home() / ".hermes"
    rutas: list[Path] = []
    for clon in data.get("clones") or []:
        for link in clon.get("links") or []:
            texto = link.get("path") or ""
            if not texto:
                continue
            expandido = Path(texto).expanduser()
            try:
                rutas.append(root / expandido.relative_to(hogar))
            except ValueError:
                rutas.append(expandido)
    return sorted(rutas)


def _piezas(root: Path) -> list[tuple[bytes, bytes]]:
    """Manifiesto normalizado, wrappers y enlaces declarados. Nada más."""
    piezas: list[tuple[bytes, bytes]] = []
    manifiesto = root / "cron" / "jobs.json"
    if manifiesto.is_file():
        leido = _pieza_manifiesto(manifiesto, root)
        if leido is not None:
            piezas.append(leido)
    scripts = root / "scripts"
    if scripts.is_dir():
        for path in sorted(p for p in scripts.rglob("*") if p.is_file()):
            leido = _pieza_archivo(path, root)
            if leido is not None:
                piezas.append(leido)
    for path in _enlaces_declarados(root):
        piezas.append(_leer_enlace(path, root))
    return piezas


def fingerprint(root: Path) -> str:
    """Huella de lo que los jobs poseen (#258).

    Cubre el manifiesto desplegado (``cron/jobs.json`` sin el libro de runtime:
    ``updated_at``, ``last_run_at``, ``next_run_at``, estado y claims), los
    wrappers de ``scripts/`` y el destino de los enlaces
    de skills declarados. El ticker, los heartbeats, ``cron/output/`` y el
    resto del runtime quedan fuera: mutan solos mientras Hermes está vivo.
    Un archivo que se esfuma entre listarlo y leerlo no rompe la corrida (#241).
    """
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for clave, datos in sorted(_piezas(root), key=lambda pieza: pieza[0]):
        digest.update(clave)
        digest.update(b"\0")
        digest.update(datos)
        digest.update(b"\0")
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
        [uv_bin(), "run", name],
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
        try:
            tipo = "huella" if ("huella" in failed or "mutó" in failed) else "codigo"
            _ledger.record_batch(
                "cron-canary",
                before,
                [{"paso": "canary", "tipo": tipo, "detalle": failed}],
                home=real,
            )
        except Exception:
            pass
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
