"""Lectura del estado vivo: drift, doctor, expectations y smoke.

No escribe el home real ni el ledger. Doctor y smoke devuelven datos;
el entrypoint imprime. El sandbox del smoke es temporal y se borra al salir.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from croniter import croniter

from cron_manifest import Job, ManifestError, normalize_target
from cron_render import render_wrapper

QUIET_DIGEST_MAX = 5
GRACE_MIN = 15  # el scheduler recupera corridas perdidas: no declarar antes
VERDICT_OK = "ok"
VERDICT_FAILED = "failed"
STATUS_OK = {"completed", "running"}
DELIVERY_OK = {None, "", "delivered", "suppressed"}

# Mutan de verdad. Mismo criterio que la deny-list del canary (#257). No se unifican aquí (#325).
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

Reader = Callable[[Path], list[dict[str, Any]]]
SmokeRunner = Callable[[list[str], dict[str, str]], subprocess.CompletedProcess[str]]
DoctorRun = Callable[[], Any]


@dataclass(frozen=True)
class DoctorReport:
    """Lo que devolvió `hermes cron doctor`. El código de salida lo decide el adaptador.

    ``ran=False`` es «no se pudo correr el doctor» (eso sí es un fallo del guard);
    ``issues=True`` es «corrió y encontró algo», que viaja como mensaje y no como rc
    (ADR 0008, #340).
    """

    ran: bool
    issues: bool
    text: str


def render_drift_digest(drift: list[str], date_str: str) -> str:
    """Digest compacto del drift para Telegram: sin tablas, <= 8 lineas."""
    lines = [f"🛡️ Cron drift — {date_str}"]
    shown = drift[:QUIET_DIGEST_MAX]
    lines += [f"- {line}" for line in shown]
    if len(drift) > len(shown):
        lines.append(f"… (+{len(drift) - len(shown)} más)")
    lines.append("remedio: bin/install-cron.sh")
    return "\n".join(lines)


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
    """`ok` | `failed` con mapa explícito, no heurística."""
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

    Solo jobs habilitados y nunca ocurrencias anteriores al alta del job.
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
    """Hallazgos del día. Lista vacía = flota sana."""
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


def read_live_jobs(hermes_home: Path) -> list[dict[str, Any]]:
    """Lee el estado real de los jobs (~/.hermes/cron/jobs.json)."""
    import json

    path = hermes_home / "cron" / "jobs.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def read_runs(hermes_home: Path, since: datetime) -> dict[str, list[dict[str, Any]]]:
    """Corridas desde `since`, agrupadas por job_id.

    Si no hay base, devuelve {}. Si la base no se puede leer, lanza ManifestError
    (el entrypoint imprime la línea en español y sigue con corridas vacías).
    """
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
        raise ManifestError(f"no se pudo leer executions.db: {exc}") from exc
    return agrupadas


def _live_signature(job: dict[str, Any]) -> dict[str, Any]:
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


def _desired_signature(job: Job, targets: dict[str, str]) -> dict[str, Any]:
    return {
        "schedule": job.schedule,
        "script": job.wrapper if job.is_no_agent else "",
        "no_agent": job.is_no_agent,
        "deliver": normalize_target(job.deliver, targets),
        "enabled": job.enabled,
        "model": job.model,
        "provider": job.provider,
    }


def _diff_signatures(desired: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    return [
        f"{key}: deseado={desired[key]!r} real={actual.get(key)!r}"
        for key in desired
        if desired[key] != actual.get(key)
    ]


def _check_wrappers(jobs: list[Job], scripts_dir: Path, repo: Path) -> list[str]:
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


def drift(
    jobs: list[Job],
    targets: dict[str, str],
    hermes_home: Path,
    repo: Path,
    read_jobs: Reader = read_live_jobs,
) -> list[str]:
    """Drift completo: wrappers + jobs, con nombres reales."""
    found = _check_wrappers(jobs, hermes_home / "scripts", repo)
    live = {str(job.get("name") or ""): job for job in read_jobs(hermes_home)}
    for job in jobs:
        real = live.get(job.name)
        if real is None:
            found.append(f"job '{job.name}': no existe en Hermes")
            continue
        found += [
            f"job '{job.name}': {line}"
            for line in _diff_signatures(_desired_signature(job, targets), _live_signature(real))
        ]
    return found


def extra_names(
    jobs: list[Job], hermes_home: Path, read_jobs: Reader = read_live_jobs
) -> list[str]:
    """Jobs reales que no están en el manifiesto (informativos, no drift)."""
    wanted = {job.name for job in jobs if job.name}
    live = {str(job.get("name") or "") for job in read_jobs(hermes_home)}
    return sorted(name for name in live if name and name not in wanted)


def signatures_differ(job: Job, targets: dict[str, str], actual: dict[str, Any]) -> list[str]:
    """Diferencias legibles entre el job deseado y uno real. La usa el read-back del apply."""
    return _diff_signatures(_desired_signature(job, targets), _live_signature(actual))


def doctor(run: DoctorRun) -> DoctorReport:
    """Salud de la flota. Sin hallazgos ni texto: `DoctorReport(True, False, "")`. No imprime."""
    try:
        result = run()
    except (OSError, subprocess.SubprocessError, ManifestError) as exc:
        return DoctorReport(ran=False, issues=False, text=f"ERROR: hermes no disponible: {exc}")
    rc = int(getattr(result, "returncode", 1) or 0)
    if rc == 0:
        return DoctorReport(ran=True, issues=False, text="")
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    out = (stdout + stderr).strip()
    text = out if out else "hermes cron doctor reportó problemas (sin detalle)"
    return DoctorReport(ran=True, issues=True, text=text)


def _smoke_env(repo: Path, sandbox: Path, home: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": SMOKE_PATH,
        "HERMES_HOME": str(sandbox),
        "HERMES_SCRIPTS_DIR": str(repo),
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


def _smoke_skip(job: Job) -> str | None:
    if not job.is_no_agent:
        return f"{job.name}: omitido (agent)"
    if job.name in SMOKE_DENY:
        return f"{job.name}: omitido (muta)"
    if not job.enabled:
        return f"{job.name}: omitido (pausado)"
    return None


def _smoke_one(
    job: Job,
    repo: Path,
    scripts: Path,
    env: dict[str, str],
    runner: SmokeRunner,
) -> tuple[int, list[str]]:
    wrapper = scripts / (job.wrapper or f"{job.name}.sh")
    wrapper.write_text(render_wrapper(job, repo), encoding="utf-8")
    try:
        proc = runner(["bash", str(wrapper)], env)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, [f"{job.name}: rc=1", f"  {exc}"]
    lines = [f"{job.name}: rc={proc.returncode}"]
    texto = "\n".join(parte for parte in (proc.stdout, proc.stderr) if parte)
    lines += [f"  {linea}" for linea in texto.splitlines()[:SMOKE_MAX_LINES]]
    return (1 if proc.returncode != 0 else 0), lines


def smoke(
    jobs: list[Job],
    repo: Path,
    runner: SmokeRunner | None = None,
    *,
    home: Path | None = None,
) -> tuple[int, list[str]]:
    """Arranca cada no_agent en un sandbox. No toca el home real. No imprime."""
    ejecutar = runner or _smoke_subprocess
    sandbox = Path(tempfile.mkdtemp(prefix="install-cron-smoke-"))
    scripts = sandbox / "scripts"
    scripts.mkdir()
    env = _smoke_env(repo, sandbox, home or Path.home())
    fallos = 0
    lines: list[str] = []
    try:
        for job in jobs:
            skipped = _smoke_skip(job)
            if skipped:
                lines.append(skipped)
                continue
            n, chunk = _smoke_one(job, repo, scripts, env, ejecutar)
            fallos += n
            lines += chunk
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    return (1 if fallos else 0), lines
