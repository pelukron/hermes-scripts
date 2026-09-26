"""Tests de src/gate_audit.py (capa pura, sin red).

Fixtures inline con la forma de los registros de `collect()`.
"""

import importlib.util
import subprocess as _subprocess
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parent.parent

from src import gate_audit as ga  # noqa: E402


def load_cli():
    """bin/gate-audit.py como modulo (tiene guion, no es importable)."""
    spec = importlib.util.spec_from_file_location("gate_audit_cli", REPO / "bin" / "gate-audit.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


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


def test_orphan_contexts_solo_los_que_nadie_produce():
    exigidos = ["test (3.11)", "test (3.12)", "closes"]
    producidos = ["test (3.11)", "test (3.13)", "closes", "notify"]
    assert ga.orphan_contexts(exigidos, producidos) == ["test (3.12)"]


def test_orphan_contexts_sin_evidencia_no_acusa():
    # sin corridas que leer no se puede afirmar huérfano: sería un falso positivo
    assert ga.orphan_contexts(["test (3.12)", "closes"], []) == []


def test_orphan_contexts_compara_literal():
    # el nombre del check se compara exacto: el espacio cuenta
    assert ga.orphan_contexts(["test (3.11)"], ["test(3.11)"]) == ["test (3.11)"]
    assert ga.orphan_contexts(["closes"], ["closes"]) == []


def test_huerfano_cuenta_como_hueco_y_va_primero():
    records = fixture_records()
    records[0]["contexts"] = ["test (3.11)", "test (3.12)"]
    records[0]["orphans"] = ["test (3.12)"]
    found = ga.gaps(records)
    assert found["pelukron/hermes-scripts"][0] == "huérfano: test (3.12)"
    assert "pelukron/hermes-scripts" in ga.summarize(records)["with_gaps"]


def test_render_markdown_detalla_contextos_y_huerfanos():
    records = fixture_records()
    records[0]["contexts"] = ["test (3.11)", "test (3.12)"]
    records[0]["orphans"] = ["test (3.12)"]
    text = ga.render_markdown(records, ga.summarize(records))
    assert "exigidos: test (3.11), test (3.12)" in text
    assert "huérfano: `test (3.12)`" in text


def test_render_digest_muestra_el_huerfano():
    records = fixture_records()
    records[0]["orphans"] = ["test (3.12)"]
    text = ga.render_digest(records, ga.summarize(records), "2026-09-25")
    assert "huérfano: test (3.12)" in text
    assert len(text.splitlines()) <= 8


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

    def test_required_contexts(self, monkeypatch):
        def fake(path, *a):
            if path.endswith("/rulesets"):
                return True, [{"id": 1}, {"id": 2}]
            if path.endswith("/rulesets/1"):
                return True, {
                    "rules": [
                        {"type": "pull_request"},
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "closes"},
                                    {"context": "audit"},
                                ]
                            },
                        },
                    ]
                }
            return False, None  # el ruleset 2 no se puede leer

        monkeypatch.setattr(ga, "_gh", fake)
        assert ga.required_contexts("o", "r") == ["closes", "audit"]

    def test_required_contexts_vacio(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.required_contexts("o", "r") == []
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, {"no": "lista"}))
        assert ga.required_contexts("o", "r") == []

    def test_produced_checks(self, monkeypatch):
        def fake(path, *a):
            if path.endswith("/actions/workflows"):
                return True, {"workflows": [{"id": 7}, {"id": 8}]}
            if path.endswith("/workflows/7/runs?per_page=1"):
                return True, {"workflow_runs": [{"id": 99}]}
            if path.endswith("/runs/99/jobs"):
                return True, {
                    "jobs": [{"name": "test (3.11)"}, {"name": "notify"}, {"name": "test (3.11)"}]
                }
            return False, None  # workflow 8: corridas ilegibles

        monkeypatch.setattr(ga, "_gh", fake)
        assert ga.produced_checks("o", "r") == ["test (3.11)", "notify"]

    def test_produced_checks_sin_workflows(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, []))
        assert ga.produced_checks("o", "r") == []

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
        monkeypatch.setattr(ga, "required_contexts", lambda o, r: ["closes", "test (3.12)"])
        monkeypatch.setattr(ga, "produced_checks", lambda o, r: ["closes", "test (3.13)"])
        (rec,) = ga.collect("o", ["r"])
        assert rec["repo"] == "o/r"
        assert rec["gate"] == "ci.yml"
        assert rec["checks"]["agents"] is True
        assert rec["checks"]["ci"] is True
        assert rec["checks"]["dependabot"] is False
        assert rec["contexts"] == ["closes", "test (3.12)"]
        assert rec["orphans"] == ["test (3.12)"]

    def test_collect_sin_contextos_no_consulta_corridas(self, monkeypatch):
        monkeypatch.setattr(ga, "repo_visibility", lambda o, r: "PRIVATE")
        monkeypatch.setattr(ga, "file_exists", lambda o, r, p: False)
        monkeypatch.setattr(ga, "list_workflows", lambda o, r: [])
        monkeypatch.setattr(ga, "ruleset_status", lambda o, r, v: "no (privado Free)")
        monkeypatch.setattr(ga, "required_contexts", lambda o, r: [])

        def boom(o, r):
            raise AssertionError("sin contextos exigidos no se consultan las corridas")

        monkeypatch.setattr(ga, "produced_checks", boom)
        (rec,) = ga.collect("o", ["r"])
        assert rec["contexts"] == []
        assert rec["orphans"] == []


class TestCliQuiet:
    """Modo job semanal (#317): silencioso si verde, digest + rc 1 con huecos."""

    def test_quiet_verde_no_imprime(self, monkeypatch, capsys):
        cli = load_cli()
        (verde,) = [r for r in fixture_records() if r["repo"] == "pelukron/hermes-scripts"]
        monkeypatch.setattr(cli, "collect", lambda o, r: [verde])
        assert cli.main(["--digest", "--quiet", "--no-write"]) == 0
        assert capsys.readouterr().out == ""

    def test_quiet_con_huecos_entrega_digest(self, monkeypatch, capsys):
        cli = load_cli()
        monkeypatch.setattr(cli, "collect", lambda o, r: fixture_records())
        assert cli.main(["--digest", "--quiet", "--no-write"]) == 1
        assert "hermes-empleo" in capsys.readouterr().out

    def test_quiet_muestra_el_huerfano(self, monkeypatch, capsys):
        cli = load_cli()
        (verde,) = [r for r in fixture_records() if r["repo"] == "pelukron/hermes-scripts"]
        verde = dict(verde, orphans=["test (3.99)"])
        monkeypatch.setattr(cli, "collect", lambda o, r: [verde])
        assert cli.main(["--digest", "--quiet", "--no-write"]) == 1
        assert "huérfano: test (3.99)" in capsys.readouterr().out
