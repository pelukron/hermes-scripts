"""bin/gh-review: cabecera, body, comentarios, dependencias y sub-issues (#243).

Hermético: un stub de `gh` en el PATH responde con las formas reales de la API,
así que no toca la red ni necesita autenticación.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "bin" / "gh-review"

ISSUE = {
    "number": 7,
    "title": "algo se rompe",
    "state": "open",
    "user": {"login": "pelukron"},
    "created_at": "2026-09-01T10:00:00Z",
    "labels": [{"name": "bug"}],
    "html_url": "https://github.com/pelukron/hermes-scripts/issues/7",
    "body": "cuerpo del issue",
}
COMMENTS = [{"user": {"login": "diego"}, "body": "primer comentario"}]
BLOCKED_BY = [{"number": 3, "state": "closed", "title": "lo que bloquea"}]
SUB_ISSUES = [{"number": 8, "state": "open", "title": "sub"}]


def _gh_stub(tmp_path: Path) -> Path:
    """Stub de gh: responde a `auth status` y a los `api` que usa el helper."""
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'case "$*" in\n'
        '  "auth status") exit 0 ;;\n'
        f"  *issues/7/comments*) printf '%s' '{json.dumps(COMMENTS)}' ;;\n"
        f"  *dependencies/blocked_by*) printf '%s' '{json.dumps(BLOCKED_BY)}' ;;\n"
        "  *dependencies/blocking*) printf '%s' '[]' ;;\n"
        f"  *sub_issues*) printf '%s' '{json.dumps(SUB_ISSUES)}' ;;\n"
        f"  *issues/7*) printf '%s' '{json.dumps(ISSUE)}' ;;\n"
        "  *) printf '%s' '{}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _run(stub_bin: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{stub_bin}:{os.environ['PATH']}"}
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60)


def test_es_ejecutable():
    assert os.access(SCRIPT, os.X_OK)


def test_es_solo_lectura():
    """El helper no debe escribir en GitHub: es de revisión."""
    texto = SCRIPT.read_text(encoding="utf-8")
    for verbo in (
        "-X POST",
        "-X PATCH",
        "-X DELETE",
        "--method POST",
        "--method PATCH",
        "--method DELETE",
        "gh issue create",
        "gh pr create",
    ):
        assert verbo not in texto


def test_sin_argumentos_muestra_el_uso(tmp_path):
    r = _run(_gh_stub(tmp_path))
    assert r.returncode == 1
    assert "Usage:" in r.stdout


def test_issue_normal_imprime_cabecera_body_y_comentarios(tmp_path):
    r = _run(_gh_stub(tmp_path), "o/r", "7")
    assert r.returncode == 0, r.stderr
    assert "=== #7 [open] algo se rompe ===" in r.stdout
    assert "autor: pelukron" in r.stdout
    assert "labels: bug" in r.stdout
    assert "cuerpo del issue" in r.stdout
    assert "[diego]: primer comentario" in r.stdout


def test_dependencias_listan_numeros(tmp_path):
    r = _run(_gh_stub(tmp_path), "o/r", "7")
    assert "blocked_by: #3" in r.stdout
    assert "blocking:" not in r.stdout


def test_epic_lista_sub_issues(tmp_path):
    r = _run(_gh_stub(tmp_path), "o/r", "7", "--epic")
    assert r.returncode == 0, r.stderr
    assert "#8 [open] sub" in r.stdout


def test_json_crudo(tmp_path):
    r = _run(_gh_stub(tmp_path), "o/r", "7", "--json")
    assert json.loads(r.stdout) == ISSUE
