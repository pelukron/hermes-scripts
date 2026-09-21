"""adopted-sha-audit (#235): historia, clasificación código/entorno, silencio en verde."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

import adopted_sha_audit as audit  # noqa: E402


def _ok(*_a, **_k):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def _fail(rc=1, stderr="boom", stdout=""):
    def inner(*_a, **_k):
        return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)

    return inner


def test_gate_env_sanea_tmpdir_y_virtual_env(tmp_path, monkeypatch):
    scratch = tmp_path / "hermes" / "cache" / "scratch"
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
    monkeypatch.setenv("TMPDIR", str(scratch))
    env = audit.gate_env()
    assert "VIRTUAL_ENV" not in env
    assert env["TMPDIR"] != str(scratch)


def test_classify_audit_sin_red_es_entorno():
    out = "pip-audit: ConnectionRefusedError: [Errno 111] Connection refused"
    assert audit.classify("audit", out) == "entorno"


def test_classify_assertion_es_codigo():
    out = "AssertionError: assert 'Debes estar en main' in '...'"
    assert audit.classify("test", out) == "codigo"


def test_parse_junit_del_fallo_real_de_main(tmp_path):
    """El rojo que #234 arregló: test_con_token_no_muere_en_la_carga es código."""
    xml = tmp_path / "junit.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" failures="1" tests="3">
    <testcase classname="tests.test_bump_and_pr" name="test_con_token_no_muere_en_la_carga">
      <failure message="AssertionError: assert 'Debes estar en main' in 'x'">trace</failure>
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )
    fallos = audit.parse_junit(xml)
    assert len(fallos) == 1
    assert fallos[0]["paso"] == "test"
    assert fallos[0]["tipo"] == "codigo"
    assert "test_con_token_no_muere_en_la_carga" in fallos[0]["detalle"]


def test_parse_junit_tmpdir_heredado_es_entorno(tmp_path):
    xml = tmp_path / "junit.xml"
    xml.write_text(
        """<?xml version="1.0"?>
<testsuite failures="1" tests="1">
  <testcase classname="tests.test_install_cron" name="test_uv_se_convierte_a_uv_bin">
    <failure message="AssertionError under ~/.hermes/cache/scratch">x</failure>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    fallos = audit.parse_junit(xml)
    assert fallos[0]["tipo"] == "entorno"


def test_append_history_una_linea_por_noche(tmp_path):
    path = tmp_path / audit.HISTORY_NAME
    rec = {
        "fecha": "2026-09-21",
        "sha_adoptado": "abc",
        "veredicto": "verde",
        "fallos": [],
        "entorno": {},
    }
    audit.append_history(path, rec)
    audit.append_history(path, {**rec, "fecha": "2026-09-22", "veredicto": "rojo"})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [r["fecha"] for r in data] == ["2026-09-21", "2026-09-22"]
    assert data[1]["veredicto"] == "rojo"


def test_verde_stdout_vacio_y_escribe_historia(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(audit, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(audit, "adopted_sha", lambda _r: "deadbeef" * 5)
    monkeypatch.setattr(audit, "run_gate", lambda *_a, **_k: [])
    assert audit.main([]) == 0
    assert capsys.readouterr().out == ""
    hist = json.loads((tmp_path / audit.HISTORY_NAME).read_text(encoding="utf-8"))
    assert hist[-1]["veredicto"] == "verde"
    assert hist[-1]["sha_adoptado"] == "deadbeef" * 5
    assert hist[-1]["fallos"] == []


def test_rojo_un_mensaje_con_tipo(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(audit, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(audit, "adopted_sha", lambda _r: "cafebabe" * 5)
    fallos = [
        {
            "paso": "test",
            "tipo": "codigo",
            "detalle": "tests.test_bump_and_pr::test_con_token_no_muere_en_la_carga",
        }
    ]
    monkeypatch.setattr(audit, "run_gate", lambda *_a, **_k: fallos)
    assert audit.main([]) == 1
    out = capsys.readouterr().out
    assert out.count("adopted-sha-audit:") == 1
    assert "[codigo]" in out
    assert "test_con_token_no_muere_en_la_carga" in out
    hist = json.loads((tmp_path / audit.HISTORY_NAME).read_text(encoding="utf-8"))
    assert hist[-1]["veredicto"] == "rojo"


def test_run_gate_clasifica_audit_sin_red(tmp_path):
    def run(paso, argv, repo, env):
        del argv, repo, env
        if paso == "audit":
            return subprocess.CompletedProcess(
                args=[],
                returncode=2,
                stdout="",
                stderr="ConnectionRefusedError: [Errno 111]",
            )
        return _ok()

    fallos = audit.run_gate(REPO, audit.gate_env(), tmp_path / "j.xml", run=run)
    assert fallos == [
        {"paso": "audit", "tipo": "entorno", "detalle": "ConnectionRefusedError: [Errno 111]"}
    ]


def test_manifiesto_declara_el_job():
    from src import install_cron as ic

    jobs = ic.parse_jobs(ic.load_manifest(REPO / ic.MANIFEST_DEFAULT))
    job = next(j for j in jobs if j.name == "adopted-sha-audit")
    assert job.schedule == audit.SCHEDULE
    assert job.is_no_agent
    assert job.wrapper == "adopted-sha-audit.sh"
    assert "src/adopted_sha_audit.py" in job.command
    sync = next(j for j in jobs if j.name == "runtime-sync")
    assert job.schedule != sync.schedule
