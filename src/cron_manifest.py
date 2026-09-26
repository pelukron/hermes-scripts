"""Contrato de cron/jobs.json: carga, esquema y validación.

La versión y las claves permitidas viven aquí. Un manifiesto viejo o con
una clave desconocida no sigue en silencio.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from croniter import croniter

MANIFEST_DEFAULT = "cron/jobs.json"

TARGETS_LOCAL_DEFAULT = "cron/targets.local.json"

TARGETS_EXAMPLE_DEFAULT = "cron/targets.example.json"

VALID_TARGET_RE = re.compile(r"^(origin|local|telegram:-?\d+)$")

ABSOLUTE_HOME_RE = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+")

TARGET_REF_RE = re.compile(r"^\$\{([A-Za-z0-9_-]+)\}$")

CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))

SCHEMA_VERSION = 1

MANIFEST_KEYS = frozenset({"version", "doc", "defaults", "jobs"})

JOB_KEYS = frozenset(
    {
        "name",
        "description",
        "schedule",
        "mode",
        "deliver",
        "enabled",
        "wrapper",
        "command",
        "prompt",
        "skills",
        "model",
        "provider",
        "requires",
    }
)

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

def check_cron_expr(expr: str) -> str | None:
    """Devuelve el error de una expresion cron de 5 campos, o None si es valida.

    El calendario lo valida croniter, la misma librería que cuenta las
    ocurrencias del doctor. Así el instalador y el monitor no discrepan.
    """
    parts = expr.split()
    if len(parts) != 5:
        return f"se esperaban 5 campos, hay {len(parts)}"
    try:
        croniter(expr)
    except (ValueError, KeyError) as exc:
        return f"cron invalido: {exc}"
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

def version_error(got: Any) -> str:
    """Un manifiesto de otra versión no sigue en silencio: dice cómo migrar."""
    return (
        f"version: se esperaba {SCHEMA_VERSION}, hay {got!r}. "
        'Migracion: escribe "version": 1 en cron/jobs.json. '
        "Una clave fuera de este contrato se rechaza, "
        "para que un esquema nuevo no pase en silencio en el resto del backlog."
    )

def unknown_key_errors(manifest: dict[str, Any]) -> list[str]:
    """Claves que este contrato no lista. Un typo o un campo nuevo no se traga."""
    errors: list[str] = []
    extra = sorted(set(manifest) - MANIFEST_KEYS)
    if extra:
        errors.append("claves desconocidas en el manifiesto: " + ", ".join(extra))
    defaults = manifest.get("defaults") or {}
    if isinstance(defaults, dict):
        extra_defaults = sorted(set(defaults) - JOB_KEYS)
        if extra_defaults:
            errors.append("claves desconocidas en defaults: " + ", ".join(extra_defaults))
    raw_jobs = manifest.get("jobs") or []
    if not isinstance(raw_jobs, list):
        return errors
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            continue
        extra_job = sorted(set(raw) - JOB_KEYS)
        if extra_job:
            label = str(raw.get("name") or "<sin nombre>")
            errors.append(f"{label}: claves desconocidas: {', '.join(extra_job)}")
    return errors

def validate_manifest(manifest: dict[str, Any], jobs: list[Job]) -> list[str]:
    """Reglas de validacion. Devuelve la lista de errores (vacia = OK)."""
    errors: list[str] = []
    if manifest.get("version") != SCHEMA_VERSION:
        errors.append(version_error(manifest.get("version")))
    errors.extend(unknown_key_errors(manifest))
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
