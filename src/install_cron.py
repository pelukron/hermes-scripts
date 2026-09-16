"""install_cron.py — aplica y verifica los cron jobs de Hermes declarados en cron/jobs.json.

Fuente de verdad: ``cron/jobs.json``. Este modulo:

1. valida el manifiesto (esquema, expresiones cron, rutas absolutas prohibidas),
2. renderiza los wrappers portables que viven en ``$HERMES_HOME/scripts/``,
3. hace upsert idempotente de los jobs con ``hermes cron create/edit``,
4. re-lee el estado real y verifica job por job (read-back).

Modos::

    python src/install_cron.py --dry-run      # plan, sin escribir nada
    python src/install_cron.py --check        # deseado vs real; exit 1 si hay drift
    python src/install_cron.py                # aplica

Los IDs de chat no se versionan: en el manifiesto las entregas son ``${nombre}``
y se resuelven desde ``cron/targets.local.json`` (ignorado por git).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_DEFAULT = "cron/jobs.json"
TARGETS_LOCAL_DEFAULT = "cron/targets.local.json"
WRAPPER_MARKER = "GENERADO por bin/install-cron.sh"
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


def parse_jobs(manifest: dict[str, Any]) -> list[Job]:
    """Normaliza las entradas del manifiesto aplicando ``defaults``."""
    defaults = manifest.get("defaults") or {}
    raw_jobs = manifest.get("jobs")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise ManifestError("el manifiesto no tiene 'jobs'")
    jobs: list[Job] = []
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            raise ManifestError(f"job invalido (no es objeto): {raw!r}")
        merged = {**defaults, **raw}
        mode = str(merged.get("mode") or "no_agent")
        if mode not in ("no_agent", "agent"):
            raise ManifestError(f"{merged.get('name')!r}: mode invalido {mode!r}")
        name = str(merged.get("name") or "")
        jobs.append(
            Job(
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
        )
    return jobs


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
        elif not job.prompt:
            errors.append(f"{label}: mode agent requiere 'prompt'")
        if ABSOLUTE_HOME_RE.search(job.command) or ABSOLUTE_HOME_RE.search(job.prompt):
            errors.append(f"{label}: ruta absoluta de home prohibida (usa $HOME)")
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
        'cd "$REPO_DIR" || exit 1\n'
        f"{prefix}{command} 2>&1\n"
    )


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


def job_args(job: Job, targets: dict[str, str], wrapper_path: str) -> list[str]:
    """Argumentos compartidos de create/edit."""
    args = [
        "--name",
        job.name,
        "--schedule",
        job.schedule,
        "--deliver",
        normalize_target(job.deliver, targets),
    ]
    if job.is_no_agent:
        args += ["--script", wrapper_path, "--no-agent"]
    else:
        args += ["--agent", "--prompt", job.prompt]
        for skill in job.skills:
            args += ["--add-skill", skill]
    args += ["--model", job.model, "--provider", job.provider]
    return args


def apply_plan(
    jobs: list[Job], targets: dict[str, str], hermes_home: Path, repo: Path, force: bool = False
) -> list[str]:
    """Aplica wrappers + jobs. Devuelve las lineas de registro."""
    log: list[str] = []
    scripts_dir = hermes_home / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    cli = hermes_cli()

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

    live = {str(job.get("name") or ""): job for job in read_live_jobs(hermes_home)}
    for job in jobs:
        real = live.get(job.name)
        if real is None:
            run([cli, "cron", "create", *job_args(job, targets, job.wrapper)])
            log.append(f"job {job.name}: creado")
        else:
            run([cli, "cron", "edit", str(real.get("id")), *job_args(job, targets, job.wrapper)])
            log.append(f"job {job.name}: editado")
        refreshed = {str(j.get("name") or ""): j for j in read_live_jobs(hermes_home)}
        actual = refreshed.get(job.name) or {}
        if not job.enabled and actual.get("enabled", True):
            run([cli, "cron", "pause", str(actual.get("id"))])
            log.append(f"job {job.name}: pausado")
        elif job.enabled and not actual.get("enabled", True):
            run([cli, "cron", "resume", str(actual.get("id"))])
            log.append(f"job {job.name}: reanudado")
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
        "--force",
        action="store_true",
        help="reemplaza wrappers existentes que no fueron generados por este instalador",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entrada: valida el manifiesto y ejecuta el modo pedido."""
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve() if args.repo else repo_root()
    hermes_home = (
        Path(args.hermes_home).expanduser() if args.hermes_home else Path.home() / ".hermes"
    )
    try:
        manifest = load_manifest(repo / args.manifest)
        targets = load_targets(repo / args.targets)
        jobs = parse_jobs(manifest)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.only:
        jobs = [job for job in jobs if job.name == args.only]
        if not jobs:
            print(f"ERROR: no hay job llamado {args.only!r}", file=sys.stderr)
            return 2

    errors = validate_manifest(manifest, jobs) + validate_repo_texts(repo)
    errors = [error for error in errors if error]
    if errors:
        print("Manifiesto invalido:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    print(f"Manifiesto OK: {len(jobs)} job(s) ({repo})")

    if args.check:
        drift = check_all(jobs, targets, hermes_home, repo)
        if drift:
            print("Drift detectado:")
            for line in drift:
                print(f"  - {line}")
            return 1
        print("Sin drift: wrappers y jobs coinciden con el manifiesto")
        return 0

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


if __name__ == "__main__":
    raise SystemExit(main())
