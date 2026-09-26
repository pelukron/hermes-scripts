"""install_cron.py — aplica y verifica los cron jobs de Hermes declarados en cron/jobs.json.

Fuente de verdad: ``cron/jobs.json``. Este modulo:

1. valida el manifiesto (esquema, expresiones cron, rutas absolutas prohibidas),
2. renderiza los wrappers portables que viven en ``$HERMES_HOME/scripts/``,
3. hace upsert idempotente de los jobs con ``hermes cron create/edit``,
4. re-lee el estado real y verifica job por job (read-back).

Modos::

    python src/install_cron.py                # --check: no escribe
    python src/install_cron.py --apply        # aplica wrappers + jobs
    python src/install_cron.py --dry-run      # plan, sin escribir nada
    python src/install_cron.py --check        # deseado vs real; exit 1 si hay drift
    python src/install_cron.py --smoke        # arranca cada no_agent en sandbox
    python src/install_cron.py --expectations # qué debía correr hoy y no corrió

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

from cron_manifest import (
    MANIFEST_DEFAULT,
    TARGETS_EXAMPLE_DEFAULT,
    TARGETS_LOCAL_DEFAULT,
    VALID_TARGET_RE,
    Job,
    ManifestError,
    check_cron_expr,
    load_manifest,
    load_targets,
    normalize_target,
    parse_job_entry,
    parse_jobs,
    repo_root,
    repo_text_files,
    required_target_keys,
    validate_job_commands,
    validate_manifest,
    validate_repo_texts,
)
from cron_monitor import (
    DELIVERY_OK,
    GRACE_MIN,
    QUIET_DIGEST_MAX,
    STATUS_OK,
    VERDICT_FAILED,
    VERDICT_OK,
    delivery_verdict,
    doctor_digest,
    expected_runs,
    occurrences_today,
    read_runs,
    render_drift_digest,
    run_doctor,
    run_expectations,
)
from cron_render import WRAPPER_MARKER, render_wrapper, sync_wrappers


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


def live_extra_names(jobs: list[Job], hermes_home: Path) -> list[str]:
    """Jobs reales que no están en el manifiesto (informativos, no drift)."""
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
    # Los extras son informativos (jobs del agente fuera del manifiesto): salen
    # como `info:` en el chequeo manual y nunca disparan el digest de --quiet.
    if args.quiet:
        if drift:
            print(render_drift_digest(drift, date.today().isoformat()))
        return 0
    if drift:
        print("Drift detectado:")
        for line in drift:
            print(f"  - {line}")
        for name in extra:
            print(f"info: job '{name}' existe en Hermes pero no en el manifiesto")
        return 1
    print("Sin drift: wrappers y jobs coinciden con el manifiesto")
    for name in extra:
        print(f"info: job '{name}' existe en Hermes pero no en el manifiesto")
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
