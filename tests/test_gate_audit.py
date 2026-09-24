"""Tests de src/gate_audit.py (capa pura, sin red).

Fixtures inline con la forma de los registros de `collect()`.
"""

import subprocess as _subprocess
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parent.parent

from src import gate_audit as ga  # noqa: E402


def fixture_records():
    """Dos repos: uno verde, uno con huecos."""
    full = {key: True for key, _ in ga.CHECKS}
    partial = dict(full)
    partial["agents"] = False
    partial["dependabot"] = False
    partial["codeowners"] = False
    return [
        {
            "repo": "pelukron/hermes-scripts",
            "visibility": "PUBLIC",
            "gate": "bin/gate.sh",
            "ruleset": "sin rulesets",
            "checks": full,
        },
        {
            "repo": "pelukron/hermes-empleo",
            "visibility": "PRIVATE",
            "gate": "scripts/hygiene.py",
            "ruleset": "no (privado Free)",
            "checks": partial,
        },
    ]


def test_summarize_cuenta_verdes_y_huecos():
    summary = ga.summarize(fixture_records())
    assert summary["total"] == 2
    assert summary["green"] == ["pelukron/hermes-scripts"]
    assert summary["with_gaps"] == ["pelukron/hermes-empleo"]
    assert summary["per_check"]["agents"] == 1
    assert summary["per_check"]["changelog"] == 2


def test_render_markdown_trae_matriz():
    records = fixture_records()
    text = ga.render_markdown(records, ga.summarize(records))
    assert "| repo | gate |" in text
    assert "pelukron/hermes-scripts" in text
    assert "bin/gate.sh" in text
    assert "✅" in text and "❌" in text


def test_gaps_lista_solo_faltantes():
    found = ga.gaps(fixture_records())
    assert "pelukron/hermes-scripts" not in found
    assert found["pelukron/hermes-empleo"] == ["AGENTS.md", "Dependabot", "CODEOWNERS"]


def test_render_digest_max_8_lineas_sin_tablas():
    records = fixture_records()
    text = ga.render_digest(records, ga.summarize(records), "2026-09-15")
    lines = text.splitlines()
    assert len(lines) <= 8
    assert "|" not in text
    assert lines[0].startswith("🛡️ Gate audit — 2026-09-15")


# ═══════════════════════════════════════════
# Capa red (fakes de subprocess, sin `gh` real)
# ═══════════════════════════════════════════


def _resp(rc=0, stdout="", exc=None):
    if exc is not None:
        raise exc
    m = MagicMock()
    m.returncode = rc
    m.stdout = stdout
    return m


class TestGh:
    def test_ok_json(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(stdout='{"a": 1}'))
        assert ga._gh("x") == (True, {"a": 1})

    def test_rc_distinto(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(rc=1))
        assert ga._gh("x") == (False, None)

    def test_oserror(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(exc=OSError("no gh")))
        assert ga._gh("x") == (False, None)

    def test_json_roto(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(stdout="no-json{{{"))
        assert ga._gh("x") == (False, None)


class TestRepoHelpers:
    def test_file_exists(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, {}))
        assert ga.file_exists("o", "r", "AGENTS.md") is True
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.file_exists("o", "r", "AGENTS.md") is False

    def test_list_workflows(self, monkeypatch):
        monkeypatch.setattr(
            ga, "_gh", lambda *a: (True, [{"name": "b.yml"}, {"name": "a.yml"}, "x"])
        )
        assert ga.list_workflows("o", "r") == ["a.yml", "b.yml"]
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, {"no": "lista"}))
        assert ga.list_workflows("o", "r") == []
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.list_workflows("o", "r") == []

    def test_repo_visibility(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(stdout='"public"\n'))
        assert ga.repo_visibility("o", "r") == "PUBLIC"
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(rc=1))
        assert ga.repo_visibility("o", "r") == "?"
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(exc=OSError("x")))
        assert ga.repo_visibility("o", "r") == "?"

    def test_ruleset_status(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, [{}, {}]))
        assert ga.ruleset_status("o", "r", "PUBLIC") == "2 ruleset(s)"
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, []))
        assert ga.ruleset_status("o", "r", "PUBLIC") == "sin rulesets"
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.ruleset_status("o", "r", "PRIVATE") == "no (privado Free)"
        assert ga.ruleset_status("o", "r", "PUBLIC") == "desconocido"

    def test_detect_gate(self):
        assert ga.detect_gate({"gate_sh": True}, []) == "bin/gate.sh"
        assert ga.detect_gate({"gates_sh": True}, []) == "bin/gates.sh"
        assert ga.detect_gate({"gate_mjs": True}, []) == "node scripts/gate.mjs"
        assert ga.detect_gate({"hygiene": True}, []) == "scripts/hygiene.py"
        assert ga.detect_gate({"makefile": True}, []) == "make check"
        assert ga.detect_gate({}, ["ci.yml"]) == "ci.yml"
        assert ga.detect_gate({}, []) == "?"

    def test_collect(self, monkeypatch):
        monkeypatch.setattr(ga, "repo_visibility", lambda o, r: "PUBLIC")
        monkeypatch.setattr(ga, "file_exists", lambda o, r, p: p == "AGENTS.md")
        monkeypatch.setattr(ga, "list_workflows", lambda o, r: ["ci.yml"])
        monkeypatch.setattr(ga, "ruleset_status", lambda o, r, v: "1 ruleset(s)")
        (rec,) = ga.collect("o", ["r"])
        assert rec["repo"] == "o/r"
        assert rec["gate"] == "ci.yml"
        assert rec["checks"]["agents"] is True
        assert rec["checks"]["ci"] is True
        assert rec["checks"]["dependabot"] is False
