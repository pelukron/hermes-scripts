"""adopted-sha-audit (#235): historia, clasificación código/entorno, silencio en verde."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from src import adopted_sha_audit as audit  # noqa: E402


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


def test_classify_sin_red_es_entorno():
    out = "pip-audit: ConnectionRefusedError: [Errno 111] Connection refused"
    assert audit.classify("gate", out) == "entorno"


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
    monkeypatch.setattr(audit, "load_ping_url", lambda: "https://hc-ping.com/u")
    pings = []
    monkeypatch.setattr(audit, "ping", lambda url, suffix="": pings.append(suffix))
    assert audit.main([]) == 0
    assert capsys.readouterr().out == ""
    assert pings == ["start", ""]
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
    monkeypatch.setattr(audit, "load_ping_url", lambda: "https://hc-ping.com/u")
    pings = []
    monkeypatch.setattr(audit, "ping", lambda url, suffix="": pings.append(suffix))
    assert audit.main([]) == 1
    out = capsys.readouterr().out
    assert out.count("adopted-sha-audit:") == 1
    assert "[codigo]" in out
    assert "test_con_token_no_muere_en_la_carga" in out
    assert pings == ["start", "fail"]
    hist = json.loads((tmp_path / audit.HISTORY_NAME).read_text(encoding="utf-8"))
    assert hist[-1]["veredicto"] == "rojo"


def test_excepcion_hace_ping_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(audit, "adopted_sha", lambda _r: "x")

    def boom(*_a, **_k):
        raise RuntimeError("cae")

    monkeypatch.setattr(audit, "run_gate", boom)
    monkeypatch.setattr(audit, "load_ping_url", lambda: "https://hc-ping.com/u")
    pings = []
    monkeypatch.setattr(audit, "ping", lambda url, suffix="": pings.append(suffix))
    try:
        audit.main([])
    except RuntimeError:
        pass
    else:
        raise AssertionError("debía relanzar")
    assert pings == ["start", "fail"]


def test_run_gate_clasifica_rojo_de_entorno(tmp_path):
    """pip-audit sin red dentro del comando único: entorno, no código (#265)."""

    def run(paso, argv, repo, env):
        del argv, repo, env
        assert paso == "gate", "el gate ya no se parte en pasos"
        return subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="",
            stderr="ConnectionRefusedError: [Errno 111]",
        )

    fallos = audit.run_gate(REPO, audit.gate_env(), tmp_path / "j.xml", run=run)
    assert fallos == [
        {"paso": "gate", "tipo": "entorno", "detalle": "ConnectionRefusedError: [Errno 111]"}
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


def test_el_gate_es_un_solo_comando(tmp_path):
    """La noche corre el mismo comando que local y CI, con el JUnit en el entorno (#265)."""
    visto = {}

    def run(paso, argv, repo, env):
        visto["paso"], visto["argv"], visto["env"] = paso, argv, env
        return _ok()

    junit = tmp_path / "junit.xml"
    assert audit.run_gate(REPO, audit.gate_env(), junit, run=run) == []

    assert visto["argv"] == ["bash", "bin/gate.sh"]
    assert visto["env"]["GATE_JUNIT"] == str(junit)
    assert visto["env"]["TMPDIR"] == "/tmp"
    assert "VIRTUAL_ENV" not in visto["env"]


def test_la_excepcion_del_audit_vive_en_el_makefile():
    """`--ignore-vuln` se mudó al target del Makefile (#265/#287).

    Sin la excepción, el e2e nocturno entregaría rojo por click todas las noches y ya
    no hay una copia en este módulo que la sostenga.
    """
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "PIP_AUDIT_IGNORES := --ignore-vuln PYSEC-2026-2132" in makefile
    assert "$(PIP_AUDIT_IGNORES)" in makefile


def test_lock_hash_acorta_y_sigue_al_contenido(tmp_path):
    """El hash de la noche es corto y cambia con el lock, no con la ruta (#267)."""
    (tmp_path / audit.LOCK_NAME).write_text("version = 1\n", encoding="utf-8")
    primero = audit.lock_hash(tmp_path)
    assert len(primero) == 12
    assert all(c in "0123456789abcdef" for c in primero)
    (tmp_path / audit.LOCK_NAME).write_text("version = 2\n", encoding="utf-8")
    assert audit.lock_hash(tmp_path) != primero


def test_lock_hash_sin_lock_es_vacio(tmp_path):
    """Sin archivo el registro no inventa un hash que no midió (#267)."""
    assert audit.lock_hash(tmp_path) == ""


def test_uv_version_lee_uv_con_la_ruta_resuelta(monkeypatch):
    """`uv_bin()`, no `"uv"` (#254): en cron el nombre relativo no resuelve."""
    visto = {}

    def run(argv, **_k):
        visto["argv"] = argv
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="uv 0.12.7\n", stderr="")

    monkeypatch.setattr(audit, "uv_bin", lambda: "/ruta/absoluta/uv")
    monkeypatch.setattr(audit.subprocess, "run", run)
    assert audit.uv_version() == "uv 0.12.7"
    assert visto["argv"] == ["/ruta/absoluta/uv", "--version"]


def test_uv_version_no_se_cae_si_uv_falla(monkeypatch):
    """El registro de la corrida no se pierde porque `uv` no esté (#267)."""

    def sin_uv(*_a, **_k):
        raise OSError("uv no está")

    monkeypatch.setattr(audit.subprocess, "run", sin_uv)
    assert audit.uv_version() == ""

    def rc1(*_a, **_k):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(audit.subprocess, "run", rc1)
    assert audit.uv_version() == ""


def test_entorno_afirma_uv_python_y_hash_del_lock(monkeypatch, tmp_path):
    """La historia guarda con qué se corrió (#267), no sólo `tmpdir`/`sys.executable`."""
    monkeypatch.setattr(audit, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(audit, "adopted_sha", lambda _r: "deadbeef" * 5)
    monkeypatch.setattr(audit, "run_gate", lambda *_a, **_k: [])
    monkeypatch.setattr(audit, "load_ping_url", lambda: "https://hc-ping.com/u")
    monkeypatch.setattr(audit, "ping", lambda url, suffix="": None)
    monkeypatch.setattr(audit, "uv_version", lambda: "uv 9.9.9")
    assert audit.main([]) == 0
    hist = json.loads((tmp_path / audit.HISTORY_NAME).read_text(encoding="utf-8"))
    entorno = hist[-1]["entorno"]
    assert entorno["uv"] == "uv 9.9.9"
    assert entorno["python"] == sys.executable
    assert entorno["python_version"] == platform.python_version()
    assert entorno["lock"] == audit.lock_hash(REPO)
    assert len(entorno["lock"]) == 12
