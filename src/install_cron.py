"""install_cron.py — aplica y verifica los cron jobs de Hermes declarados en cron/jobs.json.

Fuente de verdad: ``cron/jobs.json``. Este módulo es el adaptador: argparse, escritura
en ``$HERMES_HOME`` y el binario ``hermes``. El contrato, el texto del wrapper y la
lectura del estado vivo viven en ``cron_manifest``, ``cron_render`` y ``cron_monitor``.

Modos::

    python src/install_cron.py                # --check: no escribe
    python src/install_cron.py --apply        # aplica wrappers + jobs
    python src/install_cron.py --dry-run      # plan, sin escribir nada
    python src/install_cron.py --check        # deseado vs real; exit 1 si hay drift
    python src/install_cron.py --smoke        # arranca cada no_agent en sandbox
    python src/install_cron.py --expectations # qué debía correr hoy y no corrió

``bin/install-cron.sh`` sin modo ejecuta ``--apply``. Llamar al ``.py`` directo no muta.

Los IDs de chat no se versionan: en el manifiesto las entregas son ``${nombre}``
y se resuelven desde ``cron/targets.local.json`` (ignorado por git).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from cron_manifest import (
    ABSOLUTE_HOME_RE,
    MANIFEST_DEFAULT,
    TARGETS_EXAMPLE_DEFAULT,
    TARGETS_LOCAL_DEFAULT,
    VALID_TARGET_RE,
    Job,
    ManifestError,
    load_manifest,
    load_targets,
    parse_jobs,
    required_target_keys,
    validate,
)
from cron_monitor import (
    doctor,
    doctor_digest,
    drift,
    extra_names,
    read_live_jobs,
    read_runs,
    render_drift_digest,
    signatures_differ,
    smoke,
)
from cron_render import WRAPPER_MARKER, create_args, edit_args, render_wrapper
from hermes_common import repo_root

_MANIFEST_MODES = {"--apply", "--check", "--dry-run", "--smoke"}


def validate_repo_texts(repo: Path) -> list[str]:
    """Ningún archivo versionado del repo puede tener rutas /home/<usuario>."""
    errors: list[str] = []
    for path in _repo_text_files(repo):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ABSOLUTE_HOME_RE.search(line):
                errors.append(f"{path.relative_to(repo)}:{lineno}: ruta absoluta de home")
    return errors


def _repo_text_files(repo: Path) -> list[Path]:
    files = [repo / MANIFEST_DEFAULT, *sorted((repo / "bin").glob("*.sh"))]
    files += sorted(repo.glob("*.py"))
    files += sorted((repo / "src").rglob("*.py"))
    files += sorted((repo / "cron").glob("*.json"))
    return [path for path in files if path.is_file()]


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
    return _remove_live(job, name, cli, hermes_home)


def _remove_live(job: Job, name: str, cli: str, hermes_home: Path) -> int:
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
    return _remove_wrapper(job, hermes_home)


def _remove_wrapper(job: Job, hermes_home: Path) -> int:
    if not (job.is_no_agent and job.wrapper):
        print("(job agent: sin wrapper que borrar)")
        return 0
    target = hermes_home / "scripts" / job.wrapper
    if not target.is_file():
        return 0
    if WRAPPER_MARKER not in target.read_text(encoding="utf-8"):
        print(f"aviso: {target} sin marca generada, no se toca")
        return 0
    target.unlink()
    print(f"wrapper {job.wrapper} eliminado")
    return 0


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
        refreshed = {str(item.get("name") or ""): item for item in read_live_jobs(hermes_home)}
        actual = refreshed.get(job.name) or {}
        line = sync_job_state(job, actual, cli)
        if line is not None:
            log.append(line)
    return log


def apply_plan(
    jobs: list[Job], targets: dict[str, str], hermes_home: Path, repo: Path, force: bool = False
) -> list[str]:
    """Aplica wrappers + jobs. Devuelve las líneas de registro."""
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
        problems += [f"job '{job.name}': {line}" for line in signatures_differ(job, targets, real)]
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
        "--apply",
        action="store_true",
        help="escribe wrappers y hace upsert en Hermes; sin este flag no muta",
    )
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
        help="salud de la flota (hermes cron doctor); silencio si OK; hallazgos = mensaje, rc 0",
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
    errors = validate(manifest, jobs, repo) + validate_repo_texts(repo)
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
    found = drift(jobs, ctx.targets, ctx.hermes_home, ctx.repo, read_jobs=read_live_jobs)
    extra = extra_names(jobs, ctx.hermes_home, read_jobs=read_live_jobs)
    if args.quiet:
        if found:
            print(render_drift_digest(found, date.today().isoformat()))
        return 0
    if found:
        print("Drift detectado:")
        for line in found:
            print(f"  - {line}")
        for name in extra:
            print(f"info: job '{name}' existe en Hermes pero no en el manifiesto")
        return 1
    print("Sin drift: wrappers y jobs coinciden con el manifiesto")
    for name in extra:
        print(f"info: job '{name}' existe en Hermes pero no en el manifiesto")
    return 0


def run_smoke(ctx: RunContext, runner=None) -> int:
    """Imprime el smoke. El sandbox y el runner viven en cron_monitor.smoke."""
    code, lines = smoke(ctx.jobs, ctx.repo, runner)
    for line in lines:
        print(line)
    return int(code)


def run_apply(ctx: RunContext) -> int:
    """Modo --apply o --dry-run: avisa requires, planea o aplica."""
    args, jobs = ctx.args, ctx.jobs
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
        for line in apply_plan(jobs, ctx.targets, ctx.hermes_home, ctx.repo, force=args.force):
            print(f"  {line}")
        problems = verify(jobs, ctx.targets, ctx.hermes_home)
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


def _run_hermes_doctor() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [hermes_cli(), "cron", "doctor"],
        capture_output=True,
        text=True,
        timeout=120,
    )


def run_doctor() -> int:
    """Modo --doctor. Silencio si todo OK. El texto lo imprime este adaptador.

    Hallazgos ⇒ rc 0 y el texto viaja al `deliver` del job: la anomalía es el
    mensaje, no un fallo del guard (#340, misma política que --expectations).
    No poder correr el doctor sí falla el job (rc 2): ahí el guard está ciego.
    """
    report = doctor(_run_hermes_doctor)
    if not report.text:
        return 0
    print(report.text, file=sys.stdout if report.ran else sys.stderr)
    return 0 if report.ran else 2


def run_expectations(hermes_home: Path) -> int:
    """Modo --expectations. Silencio si está sano. Con hallazgos, rc 0 y digest.

    La anomalía es el mensaje, no un error del propio job (#165). El ledger
    lo escribe este adaptador; el monitor solo calcula el digest.
    """
    ahora = datetime.now()
    jobs = read_live_jobs(hermes_home)
    if not jobs:
        print(f"ERROR: sin jobs en {hermes_home / 'cron' / 'jobs.json'}", file=sys.stderr)
        return 2
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        runs = read_runs(hermes_home, inicio)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        runs = {}
    lineas = _expectations_digest(jobs, runs, ahora, hermes_home)
    if not lineas:
        return 0
    print(f"🩺 Cron doctor — {ahora:%Y-%m-%d %H:%M}")
    for linea in lineas:
        print(linea)
    print("remedio: hermes cron runs <job_id> · bin/install-cron.sh --check")
    return 0


def _expectations_digest(
    jobs: list[dict[str, Any]],
    runs: dict[str, list[dict[str, Any]]],
    ahora: datetime,
    hermes_home: Path,
) -> list[str]:
    lineas = list(doctor_digest(jobs, runs, ahora))
    if not lineas:
        return []
    _record_expectations(lineas, hermes_home)
    return lineas


def _record_expectations(lineas: list[str], hermes_home: Path) -> None:
    try:
        from src import regression_ledger as _ledger
    except ImportError:  # pragma: no cover
        import regression_ledger as _ledger  # type: ignore[no-redef]
    try:
        _ledger.record_batch(
            "cron-doctor-daily",
            "",
            [{"paso": "expectations", "tipo": "codigo", "detalle": linea} for linea in lineas],
            home=hermes_home,
        )
    except Exception:
        pass


def _selected_modes(args: argparse.Namespace) -> list[str]:
    flags = (
        ("--apply", args.apply),
        ("--check", args.check),
        ("--dry-run", args.dry_run),
        ("--smoke", args.smoke),
        ("--doctor", args.doctor),
        ("--expectations", args.expectations),
        ("--init-targets", args.init_targets),
        ("--remove", bool(args.remove)),
    )
    return [name for name, on in flags if on]


def _usage_error(args: argparse.Namespace) -> str | None:
    modes = _selected_modes(args)
    if len(modes) > 1:
        return "ERROR: un solo modo por invocacion (" + ", ".join(modes) + ")"
    if args.quiet and not args.check:
        return "ERROR: --quiet solo es válido con --check"
    if args.force and not args.apply:
        return "ERROR: --force solo es válido con --apply"
    modo = modes[0] if modes else "--check"
    if args.only and modo not in _MANIFEST_MODES:
        return "ERROR: --only solo vale con --apply, --check, --dry-run o --smoke"
    return None


def _reconfigure_stdout() -> None:
    try:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    except ValueError:
        pass


def _run_mode(args: argparse.Namespace) -> int:
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
    try:
        ctx = prepare_run(args)
    except _AbortError as exc:
        return exc.rc
    if args.smoke:
        return run_smoke(ctx)
    if not args.quiet:
        print(f"Manifiesto OK: {len(ctx.jobs)} job(s) ({ctx.repo})")
    if args.dry_run or args.apply:
        return run_apply(ctx)
    return run_check(ctx)


def main(argv: list[str] | None = None) -> int:
    """Entrada: sin modo, chequea. ``--apply`` es el único camino que muta."""
    args = build_parser().parse_args(argv)
    _reconfigure_stdout()
    error = _usage_error(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    return _run_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
