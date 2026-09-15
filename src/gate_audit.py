"""gate_audit.py — matriz de quality-gates por repo + digest semanal.

Dos capas separadas:

1. Puras (sin red ni filesystem): ``summarize``, ``render_markdown``,
   ``gaps`` y ``render_digest``. Reciben registros ya colectados.
2. Red (``collect``): lee via ``gh api`` y tolera 404/403 — los repos
   privados en plan Free no exponen rulesets (``403 Upgrade to GitHub Pro``).

Formato de registro::

    {"repo": "pelukron/hermes-scripts", "visibility": "PUBLIC",
     "gate": "bin/gate.sh", "ruleset": "sin rulesets",
     "checks": {"agents": True, "ci": True, ...}}
"""

from __future__ import annotations

import subprocess
from typing import Any

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
    """Cuenta aprobados por check y separa repos verdes vs con huecos."""
    per_check = {key: 0 for key, _ in CHECKS}
    green: list[str] = []
    with_gaps: list[str] = []
    for rec in records:
        checks = rec.get("checks", {})
        missing = [key for key, _ in CHECKS if not checks.get(key)]
        if missing:
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
    """Repo -> etiquetas de checks faltantes. Solo repos con huecos."""
    out: dict[str, list[str]] = {}
    for rec in records:
        checks = rec.get("checks", {})
        missing = [label for key, label in CHECKS if not checks.get(key)]
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
        result = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=False)
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
            ["gh", "api", f"repos/{owner}/{repo}", "--jq", ".visibility"],
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
        records.append(
            {
                "repo": full,
                "visibility": visibility,
                "gate": detect_gate(files, workflows),
                "ruleset": ruleset_status(owner, name, visibility),
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
