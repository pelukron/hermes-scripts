"""Testigo externo (healthchecks.io) para distinguir verde de «no corrió» (#236).

La URL no se versiona: ``HEALTHCHECK_PING_URL`` en el entorno o en
``$HERMES_HOME/.env``. Sin URL los pings son no-op (el job no revienta).

Convención de healthchecks.io: ``/start`` al arrancar, GET al UUID si
terminó bien, ``/fail`` si revienta. Un ``/start`` sin ping final alerta
cuando la caja se apaga a mitad de corrida.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from hermes_common import state_dir

ENV_KEY = "HEALTHCHECK_PING_URL"
TIMEOUT = 10

Getter = Callable[[str], None]


def ping_url(base: str, suffix: str = "") -> str:
    """``https://hc-ping.com/<uuid>`` + ``/start`` o ``/fail``."""
    root = base.rstrip("/")
    return f"{root}/{suffix}" if suffix else root


def load_ping_url(env: dict[str, str] | None = None, home: Path | None = None) -> str | None:
    """Env gana; si no, una línea ``HEALTHCHECK_PING_URL=`` en ``.env``."""
    source = env if env is not None else os.environ
    raw = (source.get(ENV_KEY) or "").strip()
    if raw:
        return raw
    env_file = (home if home is not None else state_dir()) / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{ENV_KEY}="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def ping(base: str | None, suffix: str = "", get: Getter | None = None) -> None:
    """GET best-effort. Nunca lanza: el testigo no puede tumbar la auditoría."""
    if not base:
        return
    url = ping_url(base, suffix)
    if get is None:
        import requests

        def get(u: str) -> None:
            requests.get(u, timeout=TIMEOUT)

    try:
        get(url)
    except Exception:
        return
