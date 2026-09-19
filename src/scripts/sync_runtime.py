"""sync-runtime — pone al dia los clones de runtime declarados y vigila los symlinks desplegados.

Los clones viven en `config/runtime-clones.json` (versionado, sin secretos). Nunca hace
force: si un clon divergio, lo reporta y no lo toca. Silencio cuando no hay nada que
contar, que es el contrato de los jobs no_agent del cron de Hermes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

CONFIG_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "runtime-clones.json"


def _run(args: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str]:
    """Run git with those args and return (rc, combined output)."""
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _sh(command: str, cwd: Path, timeout: int = 120) -> tuple[int, str]:
    """Run a shell command (the declared smoke test) and return (rc, combined output)."""
    proc = subprocess.run(
        ["bash", "-lc", command], cwd=cwd, capture_output=True, text=True, timeout=timeout
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _sha(repo: Path, rev: str = "HEAD") -> str:
    rc, out = _run(["rev-parse", "--short", rev], cwd=repo)
    return out if rc == 0 else ""


def load_config(path: Path) -> list[dict]:
    """Read the declared runtime clones; a malformed entry is a usage error, not silence."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    clones = raw.get("clones") if isinstance(raw, dict) else None
    if not isinstance(clones, list):
        raise ValueError('la config necesita una lista "clones"')
    for entry in clones:
        if not isinstance(entry, dict) or "name" not in entry or "path" not in entry:
            raise ValueError(f"entrada de clon invalida: {entry!r}")
    return [dict(entry) for entry in clones]


def sync_clone(entry: dict) -> dict:
    """Fast-forward one clone to its origin/<branch>; never force, never guess."""
    repo = Path(entry["path"]).expanduser()
    branch = entry.get("branch", "main")
    result = {"name": entry["name"], "path": str(repo), "status": "error", "detail": ""}
    if not (repo / ".git").is_dir():
        result["detail"] = "sin .git"
        return result

    rc, out = _run(["fetch", "--quiet", "origin", branch], cwd=repo)
    if rc != 0:
        result["detail"] = f"fetch fallo: {out[:120]}"
        return result

    result["old"] = _sha(repo)
    result["new"] = _sha(repo, f"origin/{branch}")
    ahead = _run(["rev-list", "--count", f"origin/{branch}..HEAD"], cwd=repo)[1]
    behind = _run(["rev-list", "--count", f"HEAD..origin/{branch}"], cwd=repo)[1]

    if ahead not in ("", "0"):
        result["status"] = "diverged"
        result["detail"] = f"{ahead} commit(s) locales que main no tiene"
        return result
    if behind in ("", "0"):
        result["status"] = "up-to-date"
        return result

    rc, out = _run(["pull", "--ff-only", "origin", branch], cwd=repo)
    if rc != 0:
        result["status"] = "error"
        result["detail"] = f"pull fallo: {out[:120]}"
        return result
    result["status"] = "pulled"
    result["now"] = _sha(repo)

    smoke = entry.get("smoke") or ""
    if smoke:
        result["smoke_rc"] = _sh(smoke, repo)[0]
    return result


def check_links(entry: dict) -> list[str]:
    """Report deployed symlinks that do not point inside the declared clone."""
    repo = Path(entry["path"]).expanduser()
    problems = []
    for link in entry.get("links") or []:
        path = Path(link["path"]).expanduser()
        expected = (repo / link["expect"]).resolve()
        if not path.is_symlink():
            problems.append(f"symlink {path}: no existe o no es un enlace")
            continue
        real = Path(os.path.realpath(path))
        if real != expected:
            problems.append(f"symlink {path} apunta a {real}, se esperaba {expected}")
    return problems


def render(results: list[dict], problems: list[str] | None = None) -> str:
    """One block per entry worth reporting; empty string when everything is quiet."""
    lines = []
    for r in results:
        if r["status"] == "up-to-date":
            continue
        if r["status"] == "pulled":
            extra = ""
            if r.get("smoke_rc") not in (None, 0):
                extra = f" · smoke FALLO (rc={r['smoke_rc']})"
            lines.append(f"🔄 {r['name']}: {r.get('old', '?')} -> {r.get('now', '?')}{extra}")
        elif r["status"] == "diverged":
            lines.append(
                f"⚠️ {r['name']} diverged ({r['detail']}): no lo toco"
                " · remedio: revisar ese clon a mano"
            )
        else:
            lines.append(f"❌ {r['name']}: {r.get('detail', 'sin detalle')}")
    lines.extend(problems or [])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI: sync every declared clone and print only what changed (or what broke)."""
    ap = argparse.ArgumentParser(description="Pone al dia los clones de runtime declarados")
    ap.add_argument("--config", default=str(CONFIG_DEFAULT), help="ruta de runtime-clones.json")
    ap.add_argument("--only", default="", help="sincroniza solo el clon con ese nombre")
    args = ap.parse_args(argv)

    path = Path(args.config)
    if not path.is_file():
        print(f"sync-runtime: no encontre la config {path}", file=sys.stderr)
        return 2
    try:
        entries = load_config(path)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"sync-runtime: config invalida ({exc})", file=sys.stderr)
        return 2
    if args.only:
        entries = [e for e in entries if e["name"] == args.only]
        if not entries:
            print(f"sync-runtime: no hay clon declarado con nombre {args.only}", file=sys.stderr)
            return 2

    results, problems = [], []
    for entry in entries:
        results.append(sync_clone(entry))
        problems.extend(check_links(entry))

    text = render(results, problems)
    if text:
        print(text)
    bad = any(
        r["status"] in ("diverged", "error") or r.get("smoke_rc") not in (None, 0) for r in results
    )
    return 1 if bad or problems else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
