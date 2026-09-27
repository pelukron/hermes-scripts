"""Texto del wrapper y argv de `hermes cron create/edit`. No escribe nada."""

from __future__ import annotations

from pathlib import Path

from cron_manifest import Job, normalize_target
from hermes_common import uv_shell

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
        f"{uv_shell()}"
        'cd "$REPO_DIR" || exit 1\n'
        f"{prefix}{command} 2>&1\n"
    )


def job_flags(job: Job, targets: dict[str, str], wrapper_path: str) -> list[str]:
    """Flags compartidos por `hermes cron create` y `hermes cron edit`.

    El schedule y el prompt no van aquí: `create` los recibe posicionales y `edit` como flags.
    """
    args = [
        "--name",
        job.name,
        "--deliver",
        normalize_target(job.deliver, targets),
    ]
    if job.is_no_agent:
        args += ["--script", wrapper_path, "--no-agent"]
    else:
        for skill in job.skills:
            args += ["--skill", skill]
    if job.model:
        args += ["--model", job.model]
    if job.provider:
        args += ["--provider", job.provider]
    return args


def create_args(job: Job, targets: dict[str, str], wrapper_path: str) -> list[str]:
    """argv de `hermes cron create`: `<schedule> [prompt]` son posicionales."""
    head = [job.schedule] if job.is_no_agent else [job.schedule, job.prompt]
    return [*head, *job_flags(job, targets, wrapper_path)]


def edit_args(job: Job, targets: dict[str, str], wrapper_path: str) -> list[str]:
    """argv de `hermes cron edit`: el schedule (y el prompt) van como flags."""
    head = ["--schedule", job.schedule]
    if not job.is_no_agent:
        head += ["--prompt", job.prompt]
    return [*head, *job_flags(job, targets, wrapper_path)]
