"""Wrappers que el instalador escribe en $HERMES_HOME/scripts.

La resolución de `uv` del wrapper es la misma que `hermes_common.uv_bin`:
`$UV`, después `command -v uv`, después `~/.hermes/bin/uv`.
"""

from __future__ import annotations

from pathlib import Path

from cron_manifest import Job

WRAPPER_MARKER = "GENERADO por bin/install-cron.sh"

def render_wrapper(job: Job, repo: Path) -> str:
    """Genera el wrapper portable que se instala en $HERMES_HOME/scripts/."""
    command = job.command
    if command.startswith("uv "):
        command = '"$UV_BIN" ' + command[3:]
    # El comando puede traer su propio `exec`: prefijar otro daria `exec exec ...` (rc=127).
    prefix = "" if command.startswith("exec ") else "exec "
    return (
        "#!/usr/bin/env bash\n"
        f"# {WRAPPER_MARKER} desde cron/jobs.json — no editar a mano.\n"
        f"# Job: {job.name} — {job.description}\n"
        "set -uo pipefail\n"
        "\n"
        f'REPO_DIR="${{HERMES_SCRIPTS_DIR:-{repo}}}"\n'
        'if [ ! -d "$REPO_DIR" ]; then\n'
        '  echo "install-cron: repo no encontrado en $REPO_DIR" >&2\n'
        "  exit 1\n"
        "fi\n"
        'UV_BIN="${UV:-$(command -v uv || true)}"\n'
        'if [ -z "$UV_BIN" ] || [ ! -x "$UV_BIN" ]; then UV_BIN="$HOME/.hermes/bin/uv"; fi\n'
        # El smoke de un clon corre con `bash -lc`: sin export, un `uv` a secas no existe
        # bajo el PATH minimo del cron (#270, rc=127).
        'export PATH="$(dirname "$UV_BIN"):$PATH"\n'
        'cd "$REPO_DIR" || exit 1\n'
        f"{prefix}{command} 2>&1\n"
    )

def sync_wrappers(jobs: list[Job], repo: Path, scripts_dir: Path, force: bool = False) -> list[str]:
    """Escribe wrappers generados (crea/actualiza, respeta existentes sin marca)."""
    log: list[str] = []
    rendered: dict[str, str] = {}
    for job in jobs:
        if job.is_no_agent:
            rendered.setdefault(job.wrapper, render_wrapper(job, repo))
    for name, content in sorted(rendered.items()):
        target = scripts_dir / name
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == content:
            log.append(f"wrapper {name}: sin cambios")
            continue
        if current is not None and WRAPPER_MARKER not in current and not force:
            log.append(
                f"wrapper {name}: OMITIDO (existente sin marca generada; "
                "usa --force para reemplazarlo)"
            )
            continue
        target.write_text(content, encoding="utf-8")
        target.chmod(0o755)
        log.append(f"wrapper {name}: {'actualizado' if current else 'creado'}")
    return log
