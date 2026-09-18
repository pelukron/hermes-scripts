"""sync-runtime: pone al dia los clones de runtime (ff-only) y vigila los symlinks desplegados."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import sync_runtime as sr


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _escenario(tmp_path: Path) -> tuple[Path, Path]:
    """remote (bare) + clon de runtime un commit atras."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    (work / "a.txt").write_text("1", encoding="utf-8")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-qm", "uno")
    _git(work, "branch", "-M", "main")
    _git(work, "push", "-q", "-u", "origin", "main")
    # el bare nace con HEAD -> master; sin esto el clon sale sin checkout
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")

    runtime = tmp_path / "runtime"
    subprocess.run(["git", "clone", "-q", str(remote), str(runtime)], check=True)

    (work / "a.txt").write_text("2", encoding="utf-8")
    _git(work, "commit", "-qam", "dos")
    _git(work, "push", "-q", "origin", "main")
    return remote, runtime


def _entry(runtime: Path, **over) -> dict:
    entry = {"name": "demo", "path": str(runtime), "branch": "main", "smoke": ""}
    entry.update(over)
    return entry


def test_pone_al_dia_un_clon_atras(tmp_path):
    _remote, runtime = _escenario(tmp_path)
    result = sr.sync_clone(_entry(runtime))
    assert result["status"] == "pulled"
    assert result["old"] != result["new"]
    assert _git(runtime, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_silencio_cuando_ya_esta_al_dia(tmp_path):
    _remote, runtime = _escenario(tmp_path)
    sr.sync_clone(_entry(runtime))
    result = sr.sync_clone(_entry(runtime))
    assert result["status"] == "up-to-date"
    assert sr.render([result]) == ""


def test_divergido_no_se_toca(tmp_path):
    remote, runtime = _escenario(tmp_path)
    (runtime / "local.txt").write_text("x", encoding="utf-8")
    _git(runtime, "add", "local.txt")
    _git(runtime, "commit", "-qm", "local")
    antes = _git(runtime, "rev-parse", "HEAD")
    result = sr.sync_clone(_entry(runtime))
    assert result["status"] == "diverged"
    assert _git(runtime, "rev-parse", "HEAD") == antes
    assert "diverged" in sr.render([result])
    assert (
        sr.main(["--config", str(tmp_path / "nada.json")]) == 2
    )  # config inexistente = error de uso


def test_smoke_que_falla_se_reporta(tmp_path):
    _remote, runtime = _escenario(tmp_path)
    result = sr.sync_clone(_entry(runtime, smoke="false"))
    assert result["status"] == "pulled"
    assert result["smoke_rc"] != 0
    assert "smoke" in sr.render([result])


def test_symlink_desplegado_que_apunta_fuera_se_reporta(tmp_path):
    _remote, runtime = _escenario(tmp_path)
    link = tmp_path / "skill"
    link.symlink_to(tmp_path / "otro-clon" / "skills" / "job-scout")
    entry = _entry(runtime, links=[{"path": str(link), "expect": "skills/job-scout"}])
    problems = sr.check_links(entry)
    assert problems and "symlink" in problems[0]


def test_symlink_correcto_no_reporta(tmp_path):
    _remote, runtime = _escenario(tmp_path)
    (runtime / "skills" / "job-scout").mkdir(parents=True)
    link = tmp_path / "skill"
    link.symlink_to(runtime / "skills" / "job-scout")
    entry = _entry(runtime, links=[{"path": str(link), "expect": "skills/job-scout"}])
    assert sr.check_links(entry) == []


def test_main_recorre_la_config(tmp_path, capsys):
    _remote, runtime = _escenario(tmp_path)
    cfg = tmp_path / "runtime-clones.json"
    cfg.write_text(json.dumps({"clones": [_entry(runtime)]}), encoding="utf-8")
    assert sr.main(["--config", str(cfg)]) == 0
    assert "demo" in capsys.readouterr().out
