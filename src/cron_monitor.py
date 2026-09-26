"""Doctor y expectativas: qué está mal ahora, y qué debía correr hoy.

No instala ni edita jobs. La única resolución de `hermes` para el doctor
es `install_cron.hermes_cli`, para que los tests la sustituyan en un sitio.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from croniter import croniter

from cron_manifest import ManifestError

QUIET_DIGEST_MAX = 5

def render_drift_digest(drift: list[str], date_str: str) -> str:
    """Digest compacto del drift para Telegram: sin tablas, <= 8 lineas."""
    lines = [f"🛡️ Cron drift — {date_str}"]
    shown = drift[:QUIET_DIGEST_MAX]
    lines += [f"- {line}" for line in shown]
    if len(drift) > len(shown):
        lines.append(f"… (+{len(drift) - len(shown)} más)")
    lines.append("remedio: bin/install-cron.sh")
    return "\n".join(lines)

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
    import install_cron as host

    ahora = datetime.now()
    jobs = host.read_live_jobs(hermes_home)
    if not jobs:
        print(f"ERROR: sin jobs en {hermes_home / 'cron' / 'jobs.json'}", file=sys.stderr)
        return 2
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    lineas = doctor_digest(jobs, read_runs(hermes_home, inicio), ahora)
    if not lineas:
        return 0
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
    print(f"🩺 Cron doctor — {ahora:%Y-%m-%d %H:%M}")
    for linea in lineas:
        print(linea)
    print("remedio: hermes cron runs <job_id> · bin/install-cron.sh --check")
    return 0

def run_doctor() -> int:
    """Modo --doctor: salud de la flota. Silencio si todo OK, hallazgos si no."""
    import install_cron as host

    try:
        result = host.subprocess.run(
            [host.hermes_cli(), "cron", "doctor"],
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
