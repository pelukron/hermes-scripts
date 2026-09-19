"""Contrato de carga de GITHUB_TOKEN en bin/bump-and-pr.sh (#210)."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "bin" / "bump-and-pr.sh"


def _bash():
    """Git Bash real; el stub WSL (`system32\\bash.exe`) falla sin distro."""
    for c in (
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        Path(r"C:\Program Files\Git\bin\bash.exe"),
    ):
        if c.exists():
            return str(c)
    found = shutil.which("bash")
    if found and "system32" in Path(found).as_posix().lower():
        return None
    return found


needs_bash = pytest.mark.skipif(_bash() is None, reason="bash no disponible")


def _path_sin_gh(env):
    """PATH sin `gh` para no caer al fallback de gh auth token."""
    partes = []
    for p in env.get("PATH", "").split(os.pathsep):
        if not p:
            continue
        if Path(p, "gh").exists() or Path(p, "gh.exe").exists():
            continue
        partes.append(p)
    return os.pathsep.join(partes)


def _run(env, *args):
    return subprocess.run(
        [_bash(), str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(REPO),
    )


def _env_base(home, path=None):
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env["HERMES_HOME"] = str(home)
    env["PATH"] = path if path is not None else _path_sin_gh(env)
    return env


@needs_bash
def test_sin_token_en_env_existente_imprime_error(tmp_path):
    """`.env` existe pero sin GITHUB_TOKEN: no abortar en silencio (pipefail+grep)."""
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=x\nTELEGRAM_BOT_TOKEN=y\n", encoding="utf-8")
    r = _run(_env_base(tmp_path), "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert r.returncode != 0
    assert "GITHUB_TOKEN" in combined
    assert "ERROR" in combined


@needs_bash
def test_con_token_no_muere_en_la_carga(tmp_path):
    env = _env_base(tmp_path)
    env["GITHUB_TOKEN"] = "gho_test_token_no_imprimir"
    r = _run(env, "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert "gho_test_token_no_imprimir" not in combined
    assert "GITHUB_TOKEN no encontrado" not in combined
    assert "Debes estar en main" in combined


@needs_bash
def test_fallback_gh_auth_no_imprime_el_token(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "auth" ] && [ "$2" = "token" ]; then\n'
        "  echo gho_fake_from_gh_auth\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    path = str(bin_dir) + os.pathsep + _path_sin_gh(os.environ)
    r = _run(_env_base(tmp_path, path=path), "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert "gho_fake_from_gh_auth" not in combined
    assert "GITHUB_TOKEN no encontrado" not in combined
    assert "Debes estar en main" in combined or "gh auth" in combined.lower()
