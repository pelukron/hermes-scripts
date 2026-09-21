"""Contrato de carga de GITHUB_TOKEN en bin/bump-and-pr.sh (#210).

Hermético desde #234: el script resuelve su repo con `dirname $0`, así que antes
corría siempre contra este clon y contra la rama en la que estuvieras. En un PR
(checkout detached) el guard de rama disparaba y el test pasaba; en `main` no
disparaba, el test fallaba y el push a `main` quedaba rojo — un rojo que el PR no
puede ver, porque el PR se prueba detached. Peor: al no disparar el guard, el test
dejaba que el script hiciera `git pull` sobre el clon real.

Ahora cada test ejecuta una copia del script real dentro de un repo scratch, con
la rama elegida por el test. El clon y su rama dejan de ser variables del test.
"""

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


def _scratch_repo(tmp_path, branch):
    """Repo scratch con una copia del script real y la rama que pide el test.

    El script hace `cd "$(dirname $0)"`, así que la copia manda: el escenario se
    construye aquí en vez de heredarse del clon donde corra la suite.
    """
    repo = tmp_path / "scratch"
    (repo / "bin").mkdir(parents=True)
    script = repo / "bin" / "bump-and-pr.sh"
    shutil.copy(SCRIPT, script)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q", "-b", branch], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def _run(repo, env, *args):
    return subprocess.run(
        [_bash(), str(repo / "bin" / "bump-and-pr.sh"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(repo),
    )


def _env_base(home, path=None):
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env["HERMES_HOME"] = str(home)
    if path is not None:
        env["PATH"] = path
    return env


def _gh_stub(tmp_path, body):
    """`gh` falso al frente del PATH. No borrar /usr/bin: ahí viven dirname y git."""
    bin_dir = tmp_path / "ghstub"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


@needs_bash
def test_sin_token_en_env_existente_imprime_error(tmp_path):
    """`.env` existe pero sin GITHUB_TOKEN: no abortar en silencio (pipefail+grep)."""
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=x\nTELEGRAM_BOT_TOKEN=y\n", encoding="utf-8")
    path = _gh_stub(tmp_path, "exit 1\n")
    repo = _scratch_repo(tmp_path, "main")
    r = _run(repo, _env_base(tmp_path, path=path), "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert r.returncode != 0
    assert "GITHUB_TOKEN" in combined
    assert "ERROR" in combined


@needs_bash
def test_con_token_no_muere_en_la_carga(tmp_path):
    """Con token, el guard de rama sigue vivo — y la rama la pone el test, no el clon."""
    repo = _scratch_repo(tmp_path, "no-main")
    env = _env_base(tmp_path)
    env["GITHUB_TOKEN"] = "gho_test_token_no_imprimir"
    r = _run(repo, env, "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert "gho_test_token_no_imprimir" not in combined
    assert "GITHUB_TOKEN no encontrado" not in combined
    assert "Debes estar en main" in combined


@needs_bash
def test_en_main_el_guard_no_dispara(tmp_path):
    """El otro lado del guard: en `main` el script sigue adelante (no corta con ERROR)."""
    repo = _scratch_repo(tmp_path, "main")
    env = _env_base(tmp_path)
    env["GITHUB_TOKEN"] = "gho_test_token_no_imprimir"
    r = _run(repo, env, "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert "Debes estar en main" not in combined


@needs_bash
def test_fallback_gh_auth_no_imprime_el_token(tmp_path):
    path = _gh_stub(
        tmp_path,
        'if [ "$1" = "auth" ] && [ "$2" = "token" ]; then\n'
        "  echo gho_fake_from_gh_auth\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
    )
    repo = _scratch_repo(tmp_path, "no-main")
    r = _run(repo, _env_base(tmp_path, path=path), "chore: x", "--worktree")
    combined = (r.stdout or "") + (r.stderr or "")
    assert "gho_fake_from_gh_auth" not in combined
    assert "GITHUB_TOKEN no encontrado" not in combined
    assert "Debes estar en main" in combined or "gh auth" in combined.lower()
