"""gate_audit.py — matriz de quality-gates por repo + digest semanal.

Dos capas separadas:

1. Puras (sin red ni filesystem): ``summarize``, ``render_markdown``,
   ``gaps``, ``render_digest`` y ``orphan_contexts``. Reciben registros ya colectados.
2. Red (``collect``): lee via ``gh api`` y tolera 404/403 — los repos
   privados en plan Free no exponen rulesets (``403 Upgrade to GitHub Pro``).

Formato de registro::

    {"repo": "pelukron/hermes-scripts", "visibility": "PUBLIC",
     "gate": "bin/gate.sh", "ruleset": "sin rulesets",
     "contexts": ["test (3.11)", "closes"], "orphans": [],
     "checks": {"agents": True, "ci": True, ...}}

``contexts`` son los check que el ruleset exige por nombre y ``orphans`` los que ya
ningún job produce: un huérfano deja todos los PRs en ``BLOCKED`` **sin ningún check
en rojo**, así que no aparece en ningún log (#314).
"""

from __future__ import annotations

import subprocess
from typing import Any

from hermes_common import gh_bin

DEFAULT_OWNER = "pelukron"
BACKLOG_REPOS = [
    "hermes-scripts",
    "hermes-empleo",
    "diego-moreno",
    "examen-egreso-fisica",
]

# (clave, etiqueta). Todas verificables via contents API.
CHECKS: list[tuple[str, str]] = [
    ("agents", "AGENTS.md"),
    ("ci", "CI"),
    ("dependabot", "Dependabot"),
    ("codeowners", "CODEOWNERS"),
    ("prepush", "pre-push"),
    ("changelog", "CHANGELOG"),
    ("precommit", "pre-commit"),
]

PATHS: dict[str, str] = {
    "gate_sh": "bin/gate.sh",
    "gates_sh": "bin/gates.sh",
    "agents": "AGENTS.md",
    "workflows": ".github/workflows",
    "dependabot": ".github/dependabot.yml",
    "codeowners": ".github/CODEOWNERS",
    "prepush": ".githooks/pre-push",
    "changelog": "CHANGELOG.md",
    "precommit": ".pre-commit-config.yaml",
    "makefile": "Makefile",
    "hygiene": "scripts/hygiene.py",
    "gate_mjs": "scripts/gate.mjs",
}

OK = "✅"
NO = "❌"


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Cuenta aprobados por check y separa repos verdes vs con huecos.

    Un contexto huérfano cuenta como hueco: deja los PRs sin mergear aunque la
    matriz de checks esté completa.
    """
    per_check = {key: 0 for key, _ in CHECKS}
    green: list[str] = []
    with_gaps: list[str] = []
    for rec in records:
        checks = rec.get("checks", {})
        missing = [key for key, _ in CHECKS if not checks.get(key)]
        if missing or rec.get("orphans"):
            with_gaps.append(str(rec.get("repo", "?")))
        else:
            green.append(str(rec.get("repo", "?")))
        for key in per_check:
            if checks.get(key):
                per_check[key] += 1
    return {
        "total": len(records),
        "per_check": per_check,
        "green": green,
        "with_gaps": with_gaps,
    }


def gaps(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Repo -> etiquetas de checks faltantes. Solo repos con huecos.

    El huérfano va **primero**: bloquea el merge sin rojo y es lo que no se ve en ningún log.
    """
    out: dict[str, list[str]] = {}
    for rec in records:
        checks = rec.get("checks", {})
        missing = [f"huérfano: {ctx}" for ctx in rec.get("orphans", [])]
        missing += [label for key, label in CHECKS if not checks.get(key)]
        if missing:
            out[str(rec.get("repo", "?"))] = missing
    return out


def render_markdown(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    """Matriz de gates en Markdown (para `out/gate-audit.md`)."""
    lines = ["# Gate audit", ""]
    lines.append(
        f"Repos: {summary.get('total', len(records))} · "
        f"verdes: {len(summary.get('green', []))} · "
        f"con huecos: {len(summary.get('with_gaps', []))}"
    )
    lines.append("")
    header = "| repo | gate | " + " | ".join(label for _, label in CHECKS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(CHECKS) + 2))
    for rec in records:
        checks = rec.get("checks", {})
        cells = [OK if checks.get(key) else NO for key, _ in CHECKS]
        lines.append(
            f"| {rec.get('repo', '?')} | {rec.get('gate', '?')} | " + " | ".join(cells) + " |"
        )
    lines.append("")
    for rec in records:
        lines.append(
            f"- {rec.get('repo', '?')} "
            f"({rec.get('visibility', '?')}): ruleset {rec.get('ruleset', '?')}"
        )
        contexts = rec.get("contexts") or []
        if contexts:
            lines.append(f"  - exigidos: {', '.join(contexts)}")
        for orphan in rec.get("orphans") or []:
            lines.append(f"  - ❌ huérfano: `{orphan}` (ningún job lo produce: bloquea PRs)")
    lines.append("")
    return "\n".join(lines)


def render_digest(records: list[dict[str, Any]], summary: dict[str, Any], date_str: str) -> str:
    """Digest compacto para Telegram: <= 8 lineas, sin tablas."""
    found = gaps(records)
    lines = [f"🛡️ Gate audit — {date_str}"]
    for rec in records:
        repo = str(rec.get("repo", "?"))
        short = repo.split("/")[-1]
        checks = rec.get("checks", {})
        ok_count = sum(1 for key, _ in CHECKS if checks.get(key))
        missing = found.get(repo, [])
        detail = "todo verde" if not missing else "falta: " + ", ".join(missing[:2])
        mark = OK if not missing else NO
        lines.append(f"{mark} {short}: {ok_count}/{len(CHECKS)} — {detail}")
    lines.append(
        f"Verdes: {len(summary.get('green', []))}/{summary.get('total', len(records))} · "
        "detalle: out/gate-audit.md"
    )
    return "\n".join(lines)


def _gh(*args: str) -> tuple[bool, Any]:
    """Corre `gh api ...`. Devuelve (ok, json). Nunca lanza."""
    try:
        result = subprocess.run(
            [gh_bin(), "api", *args], capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False, None
    if result.returncode != 0:
        return False, None
    import json

    try:
        return True, json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return False, None


def file_exists(owner: str, repo: str, path: str) -> bool:
    """True si `path` existe en el repo (contents API)."""
    ok, _ = _gh(f"repos/{owner}/{repo}/contents/{path}")
    return ok


def list_workflows(owner: str, repo: str) -> list[str]:
    """Nombres de workflows en `.github/workflows` (vacío si no hay)."""
    ok, data = _gh(f"repos/{owner}/{repo}/contents/.github/workflows")
    if not ok or not isinstance(data, list):
        return []
    return sorted(str(item.get("name", "")) for item in data if isinstance(item, dict))


def repo_visibility(owner: str, repo: str) -> str:
    """PUBLIC / PRIVATE / ? (si la API falla).

    Nota: `gh api --jq` imprime texto crudo (no JSON), por eso no se parsea.
    """
    try:
        result = subprocess.run(
            [gh_bin(), "api", f"repos/{owner}/{repo}", "--jq", ".visibility"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "?"
    if result.returncode != 0:
        return "?"
    return result.stdout.strip().strip('"').upper() or "?"


def ruleset_status(owner: str, repo: str, visibility: str) -> str:
    """Estado de rulesets. Privados Free → 'no (privado Free)'."""
    ok, data = _gh(f"repos/{owner}/{repo}/rulesets")
    if ok and isinstance(data, list):
        return f"{len(data)} ruleset(s)" if data else "sin rulesets"
    if visibility == "PRIVATE":
        return "no (privado Free)"
    return "desconocido"


def required_contexts(owner: str, repo: str) -> list[str]:
    """Check que los rulesets del repo exigen **por nombre**.

    Devuelve [] si no hay rulesets o si no se pueden leer (privados en plan Free
    contestan 403). Cada ruleset se lee entero: la lista de contextos viene dentro
    de la regla `required_status_checks`.
    """
    ok, data = _gh(f"repos/{owner}/{repo}/rulesets")
    if not ok or not isinstance(data, list):
        return []
    out: list[str] = []
    for ruleset in data:
        rid = ruleset.get("id") if isinstance(ruleset, dict) else None
        if rid is None:
            continue
        ok_detalle, detalle = _gh(f"repos/{owner}/{repo}/rulesets/{rid}")
        if not ok_detalle or not isinstance(detalle, dict):
            continue
        for rule in detalle.get("rules", []):
            if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
                continue
            exigidos = rule.get("parameters", {}).get("required_status_checks", [])
            for chk in exigidos:
                ctx = chk.get("context") if isinstance(chk, dict) else None
                if ctx and ctx not in out:
                    out.append(str(ctx))
    return out


def produced_checks(owner: str, repo: str) -> list[str]:
    """Nombres de check que los workflows del repo producen **de verdad**.

    Fuente: los jobs de la última corrida de cada workflow (los nombres incluyen el
    sufijo de matriz: `test (3.11)`). Un workflow sin corridas no produce nada.
    """
    ok, data = _gh(f"repos/{owner}/{repo}/actions/workflows")
    if not ok or not isinstance(data, dict):
        return []
    out: list[str] = []
    for workflow in data.get("workflows", []):
        wid = workflow.get("id") if isinstance(workflow, dict) else None
        if wid is None:
            continue
        ok_runs, runs = _gh(f"repos/{owner}/{repo}/actions/workflows/{wid}/runs?per_page=1")
        if not ok_runs or not isinstance(runs, dict):
            continue
        for run in runs.get("workflow_runs", [])[:1]:
            rid = run.get("id") if isinstance(run, dict) else None
            if rid is None:
                continue
            ok_jobs, jobs = _gh(f"repos/{owner}/{repo}/actions/runs/{rid}/jobs")
            if not ok_jobs or not isinstance(jobs, dict):
                continue
            for job in jobs.get("jobs", []):
                name = job.get("name") if isinstance(job, dict) else None
                if name and name not in out:
                    out.append(str(name))
    return out


def orphan_contexts(required: list[str], produced: list[str]) -> list[str]:
    """Contextos exigidos que ya nadie produce. Pura: sin red, se testea directo.

    La comparación es literal (los espacios cuentan): `test (3.11)` != `test(3.11)`.
    """
    return [ctx for ctx in required if ctx not in produced]


def detect_gate(files: dict[str, bool], workflows: list[str]) -> str:
    """Comando de gate conocido a partir de archivos/workflows."""
    if files.get("gate_sh"):
        return "bin/gate.sh"
    if files.get("gates_sh"):
        return "bin/gates.sh"
    if files.get("gate_mjs"):
        return "node scripts/gate.mjs"
    if files.get("hygiene"):
        return "scripts/hygiene.py"
    if files.get("makefile"):
        return "make check"
    if workflows:
        return workflows[0]
    return "?"


def collect(owner: str, repos: list[str]) -> list[dict[str, Any]]:
    """Colecta un registro por repo. Tolera 404/403 (marca False/?)."""
    records: list[dict[str, Any]] = []
    for name in repos:
        full = f"{owner}/{name}"
        visibility = repo_visibility(owner, name)
        files = {key: file_exists(owner, name, path) for key, path in PATHS.items()}
        workflows = list_workflows(owner, name)
        contexts = required_contexts(owner, name)
        # `produced_checks` cuesta 2 llamadas por workflow: sólo se paga donde hay
        # contextos exigidos que puedan quedar huérfanos.
        orphans = orphan_contexts(contexts, produced_checks(owner, name)) if contexts else []
        records.append(
            {
                "repo": full,
                "visibility": visibility,
                "gate": detect_gate(files, workflows),
                "ruleset": ruleset_status(owner, name, visibility),
                "contexts": contexts,
                "orphans": orphans,
                "checks": {
                    "agents": files["agents"],
                    "ci": bool(workflows),
                    "dependabot": files["dependabot"],
                    "codeowners": files["codeowners"],
                    "prepush": files["prepush"],
                    "changelog": files["changelog"],
                    "precommit": files["precommit"],
                },
            }
        )
    return records
