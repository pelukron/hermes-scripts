"""install_cron.py — aplica y verifica los cron jobs de Hermes declarados en cron/jobs.json.

Fuente de verdad: ``cron/jobs.json``. Este modulo:

1. valida el manifiesto (esquema, expresiones cron, rutas absolutas prohibidas),
2. renderiza los wrappers portables que viven en ``$HERMES_HOME/scripts/``,
3. hace upsert idempotente de los jobs con ``hermes cron create/edit``,
4. re-lee el estado real y verifica job por job (read-back).

Modos::

    python src/install_cron.py --dry-run      # plan, sin escribir nada
    python src/install_cron.py --check        # deseado vs real; exit 1 si hay drift
    python src/install_cron.py --smoke        # arranca cada no_agent en sandbox
    python src/install_cron.py --expectations # qué debía correr hoy y no corrió
    python src/install_cron.py                # aplica

Los IDs de chat no se versionan: en el manifiesto las entregas son ``${nombre}``
y se resuelven desde ``cron/targets.local.json`` (ignorado por git).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from croniter import croniter

MANIFEST_DEFAULT = "cron/jobs.json"
TARGETS_LOCAL_DEFAULT = "cron/targets.local.json"
TARGETS_EXAMPLE_DEFAULT = "cron/targets.example.json"
VALID_TARGET_RE = re.compile(r"^(origin|local|telegram:-?\d+)$")
WRAPPER_MARKER = "GENERADO por bin/install-cron.sh"
QUIET_DIGEST_MAX = 5
ABSOLUTE_HOME_RE = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+")
TARGET_REF_RE = re.compile(r"^\$\{([A-Za-z0-9_-]+)\}$")
CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


class ManifestError(Exception):
    """Manifiesto invalido."""


@dataclass
class Job:
    """Un job del manifiesto ya normalizado con los defaults."""

    name: str
    description: str
    schedule: str
    mode: str
    deliver: str
    enabled: bool
    wrapper: str = ""
    command: str = ""
    prompt: str = ""
    skills: list[str] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    requires: list[str] = field(default_factory=list)

    @property
    def is_no_agent(self) -> bool:
        return self.mode == "no_agent"


def repo_root() -> Path:
    """Directorio del repo (src/install_cron.py -> raiz)."""
    return Path(__file__).resolve().parent.parent


def load_manifest(path: Path) -> dict[str, Any]:
    """Lee el manifiesto JSON."""
    if not path.is_file():
        raise ManifestError(f"no existe el manifiesto: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"JSON invalido en {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: el manifiesto debe ser un objeto JSON")
    return dict(data)


def load_targets(path: Path) -> dict[str, str]:
    """Lee cron/targets.local.json (IDs de chat reales, no versionados)."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: se esperaba un objeto {{nombre: destino}}")
    return {str(k): str(v) for k, v in data.items()}


def normalize_target(value: str, targets: dict[str, str]) -> str:
    """Resuelve ``${nombre}`` contra targets.local.json; deja literales tal cual."""
    match = TARGET_REF_RE.match(value)
    if not match:
        return value
    key = match.group(1)
    if key not in targets:
        raise ManifestError(
            f"destino '${{{key}}}' sin resolver: agregalo en {TARGETS_LOCAL_DEFAULT} "
            "o usa un literal ('origin', 'local' o 'telegram:<chat_id>')"
        )
    return targets[key]


def required_target_keys(jobs: list[Job]) -> list[str]:
    """Nombres ${...} usados en deliver, en orden de aparicion."""
    keys: list[str] = []
    for job in jobs:
        match = TARGET_REF_RE.match(job.deliver or "")
        if match and match.group(1) not in keys:
            keys.append(match.group(1))
    return keys


def run_init_targets(args: argparse.Namespace, repo: Path) -> int:
    """Crea targets.local.json desde el ejemplo si falta y valida claves/valores."""
    local = repo / args.targets
    if not local.is_file():
        example = repo / TARGETS_EXAMPLE_DEFAULT
        if not example.is_file():
            print(f"ERROR: falta {example} y {local}", file=sys.stderr)
            return 2
        local.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"creado {local} desde el ejemplo: editalo con tus destinos")
    try:
        manifest = load_manifest(repo / args.manifest)
        jobs = parse_jobs(manifest)
        targets = load_targets(local)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    missing = [key for key in required_target_keys(jobs) if key not in targets]
    bad = sorted(
        key for key, value in targets.items() if key != "_doc" and not VALID_TARGET_RE.match(value)
    )
    if missing:
        print(f"ERROR: faltan destinos en {local}: {', '.join(missing)}", file=sys.stderr)
        return 1
    if bad:
        print(f"ERROR: destinos invalidos en {local}: {', '.join(bad)}", file=sys.stderr)
        return 1
    print(f"targets OK: {len(targets)} destino(s) en {local}")
    return 0


def check_cron_expr(expr: str) -> str | None:
    """Devuelve el error de una expresion cron de 5 campos, o None si es valida."""
    parts = expr.split()
    if len(parts) != 5:
        return f"se esperaban 5 campos, hay {len(parts)}"
    for idx, (part, (low, high)) in enumerate(zip(parts, CRON_RANGES, strict=True)):
        if not re.fullmatch(r"[0-9*,\-/]+", part):
            return f"campo {idx + 1} invalido: {part!r}"
        for token in part.split(","):
            head = token.split("/")[0]
            if head == "*":
                continue
            for value in head.split("-"):
                if not value.isdigit():
                    return f"campo {idx + 1} invalido: {token!r}"
                if not low <= int(value) <= high:
                    return f"campo {idx + 1} fuera de rango ({low}-{high}): {token!r}"
    return None


def parse_job_entry(raw: Any, defaults: dict[str, Any]) -> Job:
    """Normaliza una entrada del manifiesto aplicando ``defaults``."""
    if not isinstance(raw, dict):
        raise ManifestError(f"job invalido (no es objeto): {raw!r}")
    merged = {**defaults, **raw}
    mode = str(merged.get("mode") or "no_agent")
    if mode not in ("no_agent", "agent"):
        raise ManifestError(f"{merged.get('name')!r}: mode invalido {mode!r}")
    name = str(merged.get("name") or "")
    return Job(
        name=name,
        description=str(merged.get("description") or ""),
        schedule=str(merged.get("schedule") or ""),
        mode=mode,
        deliver=str(merged.get("deliver") or "origin"),
        enabled=bool(merged.get("enabled", True)),
        wrapper=str(merged.get("wrapper") or (f"{name}.sh" if name else "")),
        command=str(merged.get("command") or ""),
        prompt=str(merged.get("prompt") or ""),
        skills=[str(s) for s in (merged.get("skills") or [])],
        model=str(merged.get("model") or ""),
        provider=str(merged.get("provider") or ""),
        requires=[str(r) for r in (merged.get("requires") or [])],
    )


def parse_jobs(manifest: dict[str, Any]) -> list[Job]:
    """Normaliza las entradas del manifiesto aplicando ``defaults``."""
    defaults = manifest.get("defaults") or {}
    raw_jobs = manifest.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise ManifestError("el manifiesto no tiene 'jobs'")
    return [parse_job_entry(raw, defaults) for raw in raw_jobs]


def validate_no_agent(job: Job, label: str, wrappers: dict[str, str]) -> list[str]:
    """Reglas del modo no_agent (command/wrapper unicos, sin prompt)."""
    errors: list[str] = []
    if not job.command:
        errors.append(f"{label}: mode no_agent requiere 'command'")
    if not job.wrapper:
        errors.append(f"{label}: mode no_agent requiere 'wrapper'")
    if job.wrapper:
        previous = wrappers.get(job.wrapper)
        if previous is not None and previous != job.command:
            errors.append(f"{label}: wrapper {job.wrapper} ya declarado con otro command")
        wrappers[job.wrapper] = job.command
    if job.prompt:
        errors.append(f"{label}: mode no_agent no usa 'prompt'")
    return errors


def validate_job(job: Job, wrappers: dict[str, str]) -> list[str]:
    """Reglas de un job. Devuelve errores (vacio = OK)."""
    errors: list[str] = []
    label = job.name or "<sin nombre>"
    if not job.name:
        errors.append("hay un job sin 'name'")
    if job.schedule:
        problem = check_cron_expr(job.schedule)
        if problem:
            errors.append(f"{label}: cron '{job.schedule}' -> {problem}")
    else:
        errors.append(f"{label}: sin 'schedule'")
    if not job.deliver:
        errors.append(f"{label}: sin 'deliver'")
    if job.is_no_agent:
        errors += validate_no_agent(job, label, wrappers)
    elif not job.prompt:
        errors.append(f"{label}: mode agent requiere 'prompt'")
    if ABSOLUTE_HOME_RE.search(job.command) or ABSOLUTE_HOME_RE.search(job.prompt):
        errors.append(f"{label}: ruta absoluta de home prohibida (usa $HOME)")
    return errors


def load_project_scripts(repo: Path) -> set[str]:
    """Nombres de ``[project.scripts]`` en el pyproject del repo."""
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return set()
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return set((data.get("project") or {}).get("scripts") or {})


def command_entrypoint_error(job: Job, scripts: set[str], repo: Path) -> str | None:
    """None si el command de un no_agent resuelve a un entrypoint o script del repo."""
    cmd = job.command.strip()
    if not cmd or "$HOME" in cmd or "${HOME}" in cmd:
        return None
    parts = cmd.split()
    if len(parts) >= 3 and parts[0] == "uv" and parts[1] == "run" and parts[2] == "python":
        rel = parts[3] if len(parts) > 3 else ""
        # Solo src/: los tests usan `uv run python demo.py` en repos temporales.
        if rel.startswith("src/") and not (repo / rel).is_file():
            return f"no existe {rel}"
        return None
    if len(parts) >= 3 and parts[0] == "uv" and parts[1] == "run":
        name = parts[2]
        if scripts and name not in scripts:
            return f"entrypoint {name!r} no esta en [project.scripts]"
        return None
    if len(parts) >= 2 and parts[0] == "bash":
        rel = parts[1].strip('"')
        if rel.startswith("$"):
            return None
        if rel.startswith("bin/") and not (repo / rel).is_file():
            return f"no existe {rel}"
        return None
    return None


def validate_job_commands(jobs: list[Job], repo: Path) -> list[str]:
    """Cada no_agent apunta a un entrypoint o a un script que existe (#216)."""
    scripts = load_project_scripts(repo)
    errors: list[str] = []
    for job in jobs:
        if not job.is_no_agent:
            continue
        problem = command_entrypoint_error(job, scripts, repo)
        if problem:
            errors.append(f"{job.name}: {problem}")
    return errors


def validate_manifest(manifest: dict[str, Any], jobs: list[Job]) -> list[str]:
    """Reglas de validacion. Devuelve la lista de errores (vacia = OK)."""
    errors: list[str] = []
    if manifest.get("version") != 1:
        errors.append(f"version: se esperaba 1, hay {manifest.get('version')!r}")
    names = [job.name for job in jobs]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append(f"nombres duplicados: {', '.join(duplicates)}")
    wrappers: dict[str, str] = {}
    for job in jobs:
        errors += validate_job(job, wrappers)
    return errors


def repo_text_files(repo: Path) -> list[Path]:
    """Archivos versionados donde no se permiten rutas absolutas de home."""
    files = [repo / MANIFEST_DEFAULT, *sorted((repo / "bin").glob("*.sh"))]
    files += sorted(repo.glob("*.py"))
    files += sorted((repo / "src").rglob("*.py"))
    files += sorted((repo / "cron").glob("*.json"))
    return [path for path in files if path.is_file()]


def validate_repo_texts(repo: Path) -> list[str]:
    """Ningun archivo versionado del repo puede tener rutas /home/<usuario>."""
    errors: list[str] = []
    for path in repo_text_files(repo):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ABSOLUTE_HOME_RE.search(line):
                errors.append(f"{path.relative_to(repo)}:{lineno}: ruta absoluta de home")
    return errors


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


def render_drift_digest(drift: list[str], date_str: str) -> str:
    """Digest compacto del drift para Telegram: sin tablas, <= 8 lineas."""
    lines = [f"🛡️ Cron drift — {date_str}"]
    shown = drift[:QUIET_DIGEST_MAX]
    lines += [f"- {line}" for line in shown]
    if len(drift) > len(shown):
        lines.append(f"… (+{len(drift) - len(shown)} más)")
    lines.append("remedio: bin/install-cron.sh")
    return "\n".join(lines)


def live_extra_names(jobs: list[Job], hermes_home: Path) -> list[str]:
    """Jobs reales que no están en el manifiesto (drift: el aviso quiet los tragaba)."""
    wanted = {job.name for job in jobs if job.name}
    live = {str(job.get("name") or "") for job in read_live_jobs(hermes_home)}
    return sorted(name for name in live if name and name not in wanted)


def read_live_jobs(hermes_home: Path) -> list[dict[str, Any]]:
    """Lee el estado real de los jobs (~/.hermes/cron/jobs.json)."""
    path = hermes_home / "cron" / "jobs.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def live_signature(job: dict[str, Any]) -> dict[str, Any]:
    """Campos comparables de un job real contra el deseado."""
    schedule = job.get("schedule")
    expr = schedule.get("expr") if isinstance(schedule, dict) else ""
    return {
        "schedule": expr or "",
        "script": job.get("script") or "",
        "no_agent": bool(job.get("no_agent")),
        "deliver": job.get("deliver") or "",
        "enabled": bool(job.get("enabled", True)),
        "model": job.get("model") or "",
        "provider": job.get("provider") or "",
    }


def desired_signature(job: Job, targets: dict[str, str]) -> dict[str, Any]:
    """Campos comparables del job deseado."""
    return {
        "schedule": job.schedule,
        "script": job.wrapper if job.is_no_agent else "",
        "no_agent": job.is_no_agent,
        "deliver": normalize_target(job.deliver, targets),
        "enabled": job.enabled,
        "model": job.model,
        "provider": job.provider,
    }


def diff_signatures(desired: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Diferencias legibles entre deseado y real."""
    return [
        f"{key}: deseado={desired[key]!r} real={actual.get(key)!r}"
        for key in desired
        if desired[key] != actual.get(key)
    ]


def check_wrappers(jobs: list[Job], scripts_dir: Path, repo: Path) -> list[str]:
    """Drift de los wrappers instalados contra los renderizados."""
    drift: list[str] = []
    seen: set[str] = set()
    for job in jobs:
        if not job.is_no_agent or job.wrapper in seen:
            continue
        seen.add(job.wrapper)
        target = scripts_dir / job.wrapper
        if not target.is_file():
            drift.append(f"{job.wrapper}: falta en {scripts_dir}")
            continue
        if target.read_text(encoding="utf-8") != render_wrapper(job, repo):
            drift.append(f"{job.wrapper}: contenido distinto al renderizado")
    return drift


def check_all(jobs: list[Job], targets: dict[str, str], hermes_home: Path, repo: Path) -> list[str]:
    """Drift completo: wrappers + jobs, con nombres reales."""
    drift = check_wrappers(jobs, hermes_home / "scripts", repo)
    live = {str(job.get("name") or ""): job for job in read_live_jobs(hermes_home)}
    for job in jobs:
        real = live.get(job.name)
        if real is None:
            drift.append(f"job '{job.name}': no existe en Hermes")
            continue
        drift += [
            f"job '{job.name}': {line}"
            for line in diff_signatures(desired_signature(job, targets), live_signature(real))
        ]
    return drift


def hermes_cli() -> str:
    """Binario de Hermes a usar."""
    found = shutil.which("hermes")
    if found:
        return found
    raise ManifestError("no encontre el binario 'hermes' en el PATH")


def run(cmd: list[str]) -> None:
    """Ejecuta un comando y falla con su salida si retorna != 0."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ManifestError(
            f"fallo {' '.join(cmd[:4])}... (rc={result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def run_remove(args: argparse.Namespace, repo: Path, hermes_home: Path) -> int:
    """Baja un job: `hermes cron remove <id>` + borra su wrapper generado."""
    name = args.remove
    try:
        manifest = load_manifest(repo / args.manifest)
        jobs = parse_jobs(manifest)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    found = [job for job in jobs if job.name == name]
    if not found:
        print(f"ERROR: no hay job llamado {name!r} en el manifiesto", file=sys.stderr)
        return 2
    job = found[0]
    try:
        cli = hermes_cli()
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    live = {str(item.get("name") or ""): item for item in read_live_jobs(hermes_home)}
    real = live.get(name)
    job_id = real.get("id") if isinstance(real, dict) else None
    if job_id is not None:
        try:
            run([cli, "cron", "remove", str(job_id)])
        except ManifestError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"job '{name}' eliminado de Hermes")
    else:
        print(f"aviso: job '{name}' no existe en Hermes (solo wrapper)")
    if job.is_no_agent and job.wrapper:
        target = hermes_home / "scripts" / job.wrapper
        if target.is_file():
            if WRAPPER_MARKER not in target.read_text(encoding="utf-8"):
                print(f"aviso: {target} sin marca generada, no se toca")
                return 0
            target.unlink()
            print(f"wrapper {job.wrapper} eliminado")
    else:
        print("(job agent: sin wrapper que borrar)")
    return 0


def job_flags(job: Job, targets: dict[str, str], wrapper_path: str) -> list[str]:
    """Flags compartidos por `hermes cron create` y `hermes cron edit`.

    El schedule y el prompt NO van aqui: `create` los recibe posicionales y `edit` como flags
    (ver create_args/edit_args). Un flag fuera del contrato del CLI aborta el apply con rc=2.
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
    """argv de `hermes cron create`: `<schedule> [prompt]` son POSICIONALES."""
    head = [job.schedule] if job.is_no_agent else [job.schedule, job.prompt]
    return [*head, *job_flags(job, targets, wrapper_path)]


def edit_args(job: Job, targets: dict[str, str], wrapper_path: str) -> list[str]:
    """argv de `hermes cron edit`: el schedule (y el prompt) si van como flags."""
    head = ["--schedule", job.schedule]
    if not job.is_no_agent:
        head += ["--prompt", job.prompt]
    return [*head, *job_flags(job, targets, wrapper_path)]


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


def sync_job_state(job: Job, actual: dict[str, Any], cli: str) -> str | None:
    """Pausa/reanuda el job si su estado real difiere del manifiesto."""
    if not job.enabled and actual.get("enabled", True):
        run([cli, "cron", "pause", str(actual.get("id"))])
        return f"job {job.name}: pausado"
    if job.enabled and not actual.get("enabled", True):
        run([cli, "cron", "resume", str(actual.get("id"))])
        return f"job {job.name}: reanudado"
    return None


def sync_jobs(jobs: list[Job], targets: dict[str, str], hermes_home: Path, cli: str) -> list[str]:
    """Crea/edita jobs en Hermes y concilia su estado. Devuelve el registro."""
    log: list[str] = []
    live = {str(job.get("name") or ""): job for job in read_live_jobs(hermes_home)}
    for job in jobs:
        real = live.get(job.name)
        if real is None:
            run([cli, "cron", "create", *create_args(job, targets, job.wrapper)])
            log.append(f"job {job.name}: creado")
        else:
            run([cli, "cron", "edit", str(real.get("id")), *edit_args(job, targets, job.wrapper)])
            log.append(f"job {job.name}: editado")
        refreshed = {str(j.get("name") or ""): j for j in read_live_jobs(hermes_home)}
        actual = refreshed.get(job.name) or {}
        line = sync_job_state(job, actual, cli)
        if line is not None:
            log.append(line)
    return log


def apply_plan(
    jobs: list[Job], targets: dict[str, str], hermes_home: Path, repo: Path, force: bool = False
) -> list[str]:
    """Aplica wrappers + jobs. Devuelve las lineas de registro."""
    scripts_dir = hermes_home / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    log = sync_wrappers(jobs, repo, scripts_dir, force)
    log += sync_jobs(jobs, targets, hermes_home, hermes_cli())
    return log


def verify(jobs: list[Job], targets: dict[str, str], hermes_home: Path) -> list[str]:
    """Read-back: estado real tras aplicar."""
    live = {str(job.get("name") or ""): job for job in read_live_jobs(hermes_home)}
    problems: list[str] = []
    for job in jobs:
        real = live.get(job.name)
        if real is None:
            problems.append(f"job '{job.name}': no quedo registrado")
            continue
        problems += [
            f"job '{job.name}': {line}"
            for line in diff_signatures(desired_signature(job, targets), live_signature(real))
        ]
    return problems


def build_parser() -> argparse.ArgumentParser:
    """CLI."""
    parser = argparse.ArgumentParser(
        description="Instala/verifica los cron jobs de Hermes desde cron/jobs.json"
    )
    parser.add_argument("--manifest", default=MANIFEST_DEFAULT)
    parser.add_argument("--targets", default=TARGETS_LOCAL_DEFAULT)
    parser.add_argument("--repo", default="")
    parser.add_argument("--hermes-home", default="")
    parser.add_argument("--only", default="", help="limita a un job por nombre")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="solo con --check: sin drift no imprime nada; con drift imprime digest y rc 0",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reemplaza wrappers existentes que no fueron generados por este instalador",
    )
    parser.add_argument(
        "--init-targets",
        action="store_true",
        help="crea targets.local.json desde el ejemplo si falta y valida claves/valores",
    )
    parser.add_argument(
        "--remove",
        default="",
        metavar="NAME",
        help="baja un job (hermes cron remove + borra su wrapper generado)",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="salud de la flota Hermes (hermes cron doctor); silencio si todo OK",
    )
    parser.add_argument(
        "--expectations",
        action="store_true",
        help="qué debía correr hoy y no corrió (corridas y entregas); silencio si todo OK",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="corre cada job no_agent en un sandbox; no escribe en el estado real",
    )
    return parser


# ── Expectativas del día (#217) ───────────────────────────────────────────────
#
# El doctor semanal pregunta "¿qué está mal ahora?"; esto pregunta "¿qué debía
# haber corrido hoy y no corrió?". Las cuatro reglas de abajo salen del spike del
# 2026-09-18: el chequeo ingenuo daba 356 falsos positivos y no veía las
# entregas fallidas (la clase de fallo silencioso que costó el diario de #212).

GRACE_MIN = 15  # el scheduler recupera corridas perdidas: no declarar antes
VERDICT_OK = "ok"
VERDICT_FAILED = "failed"
STATUS_OK = {"completed", "running"}
DELIVERY_OK = {None, "", "delivered", "suppressed"}


def occurrences_today(expr: str, now: datetime, grace_min: int = GRACE_MIN) -> list[datetime]:
    """Ocurrencias de hoy ya vencidas, con la ventana de gracia descontada.

    `croniter.get_next` no cuenta la hora base: sin arrancar un minuto antes,
    `*/30 * * * *` a las 11:00 devolvía 21 en vez de 22.
    """
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    iterador = croniter(expr, base - timedelta(minutes=1))
    limite = now - timedelta(minutes=grace_min)
    salida: list[datetime] = []
    while True:
        siguiente = iterador.get_next(datetime)
        if siguiente.date() != now.date() or siguiente > limite:
            break
        salida.append(siguiente)
    return salida


def delivery_verdict(status: str | None, delivery_outcome: str | None) -> str:
    """`ok` | `failed` con mapa explícito, no heurística.

    `suppressed` (los jobs silenciosos, la mayoría de las corridas) y
    `delivery_outcome` nulo son sanos; solo `failed` no lo es.
    """
    if status not in STATUS_OK:
        return VERDICT_FAILED
    if delivery_outcome in DELIVERY_OK:
        return VERDICT_OK
    return VERDICT_FAILED


def _local_ts(value: Any) -> datetime | None:
    """Marca de tiempo ISO (con o sin zona) → datetime local naive."""
    if isinstance(value, datetime):
        return value.astimezone().replace(tzinfo=None) if value.tzinfo else value
    if not isinstance(value, str) or not value:
        return None
    try:
        marca = datetime.fromisoformat(value)
    except ValueError:
        return None
    if marca.tzinfo is not None:
        marca = marca.astimezone().replace(tzinfo=None)
    return marca


def expected_runs(
    jobs: list[dict[str, Any]], now: datetime, grace_min: int = GRACE_MIN
) -> dict[str, list[datetime]]:
    """{job_id: ocurrencias esperadas hoy}.

    Solo jobs habilitados y nunca ocurrencias anteriores al alta del job: uno
    creado hoy a las 09:50 no debe nada de las 04:00.
    """
    esperadas: dict[str, list[datetime]] = {}
    for job in jobs:
        if not job.get("enabled"):
            continue
        schedule = job.get("schedule")
        expr = schedule.get("expr") if isinstance(schedule, dict) else None
        if not isinstance(expr, str) or not expr:
            continue
        ocurrencias = occurrences_today(expr, now, grace_min)
        if not ocurrencias:
            continue
        alta = _local_ts(job.get("created_at"))
        if alta is not None:
            ocurrencias = [ocurrencia for ocurrencia in ocurrencias if ocurrencia >= alta]
        if ocurrencias:
            esperadas[str(job.get("id") or "")] = ocurrencias
    return esperadas


def _covers(corrida: dict[str, Any], ocurrencia: datetime, grace_min: int = GRACE_MIN) -> bool:
    """¿Esta corrida cubre esa ocurrencia? El catch-up llega tarde, no temprano."""
    instante = corrida.get("scheduled_instant") or corrida.get("started_at")
    if not isinstance(instante, datetime):
        return False
    delta = (instante - ocurrencia).total_seconds()
    return -60 <= delta <= grace_min * 60


def doctor_digest(
    jobs: list[dict[str, Any]],
    runs: dict[str, list[dict[str, Any]]],
    now: datetime,
    grace_min: int = GRACE_MIN,
) -> list[str]:
    """Hallazgos del día. Lista vacía = flota sana (y el job no entrega nada)."""
    nombres = {str(job.get("id") or ""): str(job.get("name") or "?") for job in jobs}
    lineas: list[str] = []
    for job_id, ocurrencias in sorted(expected_runs(jobs, now, grace_min).items()):
        corridas = runs.get(job_id, [])
        for ocurrencia in ocurrencias:
            if not any(_covers(corrida, ocurrencia, grace_min) for corrida in corridas):
                lineas.append(f"- {nombres[job_id]}: sin corrida de las {ocurrencia:%H:%M}")
    for job_id, corridas in sorted(runs.items()):
        nombre = nombres.get(job_id, job_id)
        for corrida in corridas:
            veredicto = delivery_verdict(corrida.get("status"), corrida.get("delivery_outcome"))
            if veredicto == VERDICT_OK:
                continue
            hora = corrida.get("started_at")
            marca = f"{hora:%H:%M}" if isinstance(hora, datetime) else "?"
            if corrida.get("status") in STATUS_OK:
                lineas.append(f"- {nombre}: entrega fallida en la corrida de las {marca}")
            else:
                lineas.append(f"- {nombre}: corrida {corrida.get('status')} a las {marca}")
    return lineas


def read_runs(hermes_home: Path, since: datetime) -> dict[str, list[dict[str, Any]]]:
    """Corridas desde `since`, agrupadas por job_id (vacío si no hay base)."""
    db = hermes_home / "cron" / "executions.db"
    if not db.is_file():
        return {}
    agrupadas: dict[str, list[dict[str, Any]]] = {}
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conexion:
            filas = conexion.execute(
                "select job_id, started_at, scheduled_instant, status, delivery_outcome"
                " from executions where started_at >= ?",
                (since.isoformat(),),
            )
            for job_id, started_at, scheduled_instant, status, entrega in filas:
                agrupadas.setdefault(str(job_id), []).append(
                    {
                        "started_at": _local_ts(started_at),
                        "scheduled_instant": _local_ts(scheduled_instant),
                        "status": status,
                        "delivery_outcome": entrega,
                    }
                )
    except sqlite3.Error as exc:
        print(f"ERROR: no se pudo leer executions.db: {exc}", file=sys.stderr)
        return {}
    return agrupadas


def run_expectations(hermes_home: Path) -> int:
    """Modo --expectations: lo que debía correr hoy y no corrió.

    Silencio si todo está sano. Con hallazgos entrega el digest y deja el job
    VERDE: la anomalía es el mensaje, no un error del propio job (misma lección
    que el health gate de job-scout, #165).
    """
    ahora = datetime.now()
    jobs = read_live_jobs(hermes_home)
    if not jobs:
        print(f"ERROR: sin jobs en {hermes_home / 'cron' / 'jobs.json'}", file=sys.stderr)
        return 2
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    lineas = doctor_digest(jobs, read_runs(hermes_home, inicio), ahora)
    if not lineas:
        return 0
    print(f"🩺 Cron doctor — {ahora:%Y-%m-%d %H:%M}")
    for linea in lineas:
        print(linea)
    print("remedio: hermes cron runs <job_id> · bin/install-cron.sh --check")
    return 0


def run_doctor() -> int:
    """Modo --doctor: salud de la flota. Silencio si todo OK, hallazgos si no."""
    try:
        result = subprocess.run(
            [hermes_cli(), "cron", "doctor"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError, ManifestError) as exc:
        print(f"ERROR: hermes no disponible: {exc}", file=sys.stderr)
        return 2
    if result.returncode != 0:
        out = ((result.stdout or "") + (result.stderr or "")).strip()
        print(out if out else "hermes cron doctor reportó problemas (sin detalle)")
        return result.returncode or 1
    return 0


class _AbortError(Exception):
    """Salida temprana de prepare_run con su código de retorno."""

    def __init__(self, rc: int):
        super().__init__(rc)
        self.rc = rc


@dataclass
class RunContext:
    """Todo lo que los modos necesitan tras validar el manifiesto."""

    args: argparse.Namespace
    repo: Path
    hermes_home: Path
    manifest: dict[str, Any]
    targets: dict[str, str]
    jobs: list[Job]


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Repo y home efectivos desde flags o defaults."""
    repo = Path(args.repo).resolve() if args.repo else repo_root()
    hermes_home = (
        Path(args.hermes_home).expanduser() if args.hermes_home else Path.home() / ".hermes"
    )
    return repo, hermes_home


def prepare_run(args: argparse.Namespace) -> RunContext:
    """Carga y valida manifiesto + targets + jobs. Falla con _AbortError(rc)."""
    repo, hermes_home = resolve_paths(args)
    try:
        manifest = load_manifest(repo / args.manifest)
        targets = load_targets(repo / args.targets)
        jobs = parse_jobs(manifest)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise _AbortError(2) from exc
    if args.only:
        jobs = [job for job in jobs if job.name == args.only]
        if not jobs:
            print(f"ERROR: no hay job llamado {args.only!r}", file=sys.stderr)
            raise _AbortError(2)
    errors = (
        validate_manifest(manifest, jobs)
        + validate_repo_texts(repo)
        + validate_job_commands(jobs, repo)
    )
    errors = [error for error in errors if error]
    if errors:
        print("Manifiesto invalido:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        raise _AbortError(2)
    return RunContext(args, repo, hermes_home, manifest, targets, jobs)


def run_check(ctx: RunContext) -> int:
    """Modo --check: compara real vs manifiesto. 0 OK, 1 con drift."""
    args, jobs = ctx.args, ctx.jobs
    targets, hermes_home, repo = ctx.targets, ctx.hermes_home, ctx.repo
    drift = check_all(jobs, targets, hermes_home, repo)
    extra = live_extra_names(jobs, hermes_home)
    drift += [f"job '{name}': existe en Hermes pero no en el manifiesto" for name in extra]
    if args.quiet:
        if drift:
            print(render_drift_digest(drift, date.today().isoformat()))
        return 0
    if drift:
        print("Drift detectado:")
        for line in drift:
            print(f"  - {line}")
        return 1
    print("Sin drift: wrappers y jobs coinciden con el manifiesto")
    return 0


# Mutan de verdad. Mismo criterio que la deny-list del canary (#257).
SMOKE_DENY = frozenset(
    {
        "backup-diario",
        "cleanup-housekeeping",
        "runtime-sync",
        "sync-runtime",
    }
)
SMOKE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SMOKE_MAX_LINES = 8
SMOKE_TIMEOUT = 300


def smoke_env(repo: Path, sandbox: Path, home: Path) -> dict[str, str]:
    """Entorno mínimo de cron: HOME real (ahí está uv), estado y repo explícitos."""
    return {
        "HOME": str(home),
        "PATH": SMOKE_PATH,
        "HERMES_HOME": str(sandbox),
        "HERMES_SCRIPTS_DIR": str(repo),
        # B108: el sandbox del cron necesita un TMPDIR real y estable.
        "TMPDIR": "/tmp",  # nosec B108
    }


def _smoke_subprocess(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=env.get("HERMES_SCRIPTS_DIR") or None,
        env=env,
        capture_output=True,
        text=True,
        timeout=SMOKE_TIMEOUT,
    )


def run_smoke(ctx: RunContext, runner=None) -> int:
    """Arranca cada no_agent en un sandbox. 1 si alguno sale distinto de 0.

    No toca ``ctx.hermes_home``: el estado va a un temporal. HOME sigue siendo
    el del operador para resolver ``~/.hermes/bin/uv``. Sin el flag, nada de esto corre.
    """
    ejecutar = runner or _smoke_subprocess
    sandbox = Path(tempfile.mkdtemp(prefix="install-cron-smoke-"))
    scripts = sandbox / "scripts"
    scripts.mkdir()
    env = smoke_env(ctx.repo, sandbox, Path.home())
    fallos = 0
    try:
        for job in ctx.jobs:
            if not job.is_no_agent:
                print(f"{job.name}: omitido (agent)")
                continue
            if job.name in SMOKE_DENY:
                print(f"{job.name}: omitido (muta)")
                continue
            if not job.enabled:
                print(f"{job.name}: omitido (pausado)")
                continue
            wrapper = scripts / (job.wrapper or f"{job.name}.sh")
            wrapper.write_text(render_wrapper(job, ctx.repo), encoding="utf-8")
            try:
                proc = ejecutar(["bash", str(wrapper)], env)
            except (OSError, subprocess.SubprocessError) as exc:
                print(f"{job.name}: rc=1")
                print(f"  {exc}")
                fallos += 1
                continue
            print(f"{job.name}: rc={proc.returncode}")
            texto = "\n".join(parte for parte in (proc.stdout, proc.stderr) if parte)
            for linea in texto.splitlines()[:SMOKE_MAX_LINES]:
                print(f"  {linea}")
            if proc.returncode != 0:
                fallos += 1
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    return 1 if fallos else 0


def run_apply(ctx: RunContext) -> int:
    """Modo por defecto (+ --dry-run): avisa requires, planea o aplica."""
    args, jobs = ctx.args, ctx.jobs
    targets, hermes_home, repo = ctx.targets, ctx.hermes_home, ctx.repo
    for job in jobs:
        for path in job.requires:
            expanded = Path(path.replace("$HOME", str(Path.home())))
            if not expanded.exists():
                print(f"AVISO: {job.name}: falta {expanded} (job se omite)")
    if args.dry_run:
        for job in jobs:
            destino = job.wrapper if job.is_no_agent else "agent (LLM)"
            print(f"  - {job.name}: {job.schedule} -> {destino}")
        print("Dry-run: no se escribio nada")
        return 0
    try:
        for line in apply_plan(jobs, targets, hermes_home, repo, force=args.force):
            print(f"  {line}")
        problems = verify(jobs, targets, hermes_home)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if problems:
        print("Verificacion con diferencias:")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("Verificado: estado real == manifiesto")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrada: valida el manifiesto y ejecuta el modo pedido."""
    args = build_parser().parse_args(argv)
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):  # consolas Windows (cp1252)
            reconfigure(encoding="utf-8")
    except ValueError:
        pass
    if args.init_targets:
        repo = Path(args.repo).resolve() if args.repo else repo_root()
        return run_init_targets(args, repo)
    if args.remove:
        repo = Path(args.repo).resolve() if args.repo else repo_root()
        hermes_home = (
            Path(args.hermes_home).expanduser() if args.hermes_home else Path.home() / ".hermes"
        )
        return run_remove(args, repo, hermes_home)
    if args.expectations:
        hermes_home = (
            Path(args.hermes_home).expanduser() if args.hermes_home else Path.home() / ".hermes"
        )
        return run_expectations(hermes_home)
    if args.doctor:
        return run_doctor()
    if args.quiet and not args.check:
        print("ERROR: --quiet solo es válido con --check", file=sys.stderr)
        return 2
    try:
        ctx = prepare_run(args)
    except _AbortError as exc:
        return exc.rc
    if args.smoke:
        return run_smoke(ctx)
    if not args.quiet:
        print(f"Manifiesto OK: {len(ctx.jobs)} job(s) ({ctx.repo})")
    if args.check:
        return run_check(ctx)
    return run_apply(ctx)


if __name__ == "__main__":
    raise SystemExit(main())
