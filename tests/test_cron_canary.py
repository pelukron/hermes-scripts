"""cron-canary (#218, #258): sandbox, huella de lo poseído, silencio en verde, 1 mensaje."""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

import cron_canary as cc  # noqa: E402


def test_allow_y_deny_no_se_solapan():
    assert not set(cc.ALLOW_LIST) & set(cc.DENY_LIST)
    assert "monitor-ram-mexico" in cc.ALLOW_LIST
    assert "backup-diario" in cc.DENY_LIST


def test_payload_cabe_en_un_mensaje():
    text = cc.canary_payload()
    assert 0 < cc.utf16_len(text) <= cc.TELEGRAM_UTF16_LIMIT


def test_fingerprint_cambia_si_mutan_un_wrapper(tmp_path):
    """Un wrapper editado a mano sí es mutación: la huella tiene que verlo (#258)."""
    wrapper = tmp_path / "scripts" / "cron-canary.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    before = cc.fingerprint(tmp_path)
    wrapper.write_text("#!/bin/sh\necho pwn\n", encoding="utf-8")
    assert cc.fingerprint(tmp_path) != before


def test_fingerprint_cuenta_manifiesto_corrupto(tmp_path):
    """Un jobs.json ilegible no se normaliza: la corrupción sigue siendo mutación."""
    jobs = tmp_path / "cron" / "jobs.json"
    jobs.parent.mkdir(parents=True)
    jobs.write_text("{", encoding="utf-8")
    before = cc.fingerprint(tmp_path)
    jobs.write_text("{ ", encoding="utf-8")
    assert cc.fingerprint(tmp_path) != before


def test_fingerprint_cambia_si_muta_el_manifiesto(tmp_path):
    """Un comando distinto en jobs.json cuenta; el latido, no (eso lo cubre el otro test)."""
    jobs = tmp_path / "cron" / "jobs.json"
    jobs.parent.mkdir(parents=True)
    jobs.write_text('{"jobs":[{"name":"a","command":"uv run a"}]}', encoding="utf-8")
    before = cc.fingerprint(tmp_path)
    jobs.write_text('{"jobs":[{"name":"a","command":"uv run b"}]}', encoding="utf-8")
    assert cc.fingerprint(tmp_path) != before


def test_fingerprint_sigue_el_enlace_no_el_cuerpo_del_skill(tmp_path, monkeypatch):
    """Reapuntar un enlace declarado muta; editar el SKILL.md del clon, no (#258)."""
    destino = tmp_path / "clon" / "skills" / "github-pelukron-flow"
    destino.mkdir(parents=True)
    (destino / "SKILL.md").write_text("name: github-pelukron-flow\n", encoding="utf-8")
    link = tmp_path / "skills" / "github" / "github-pelukron-flow"
    link.parent.mkdir(parents=True)
    otro = tmp_path / "otro-clon"
    otro.mkdir()
    apuntados = {link: destino}
    try:
        link.symlink_to(destino, target_is_directory=True)
        real = True
    except OSError:
        real = False

        def es_enlace(self: Path) -> bool:
            return self in apuntados

        def destino_de(path: str | Path) -> str:
            return os.fspath(apuntados[Path(path)])

        monkeypatch.setattr(Path, "is_symlink", es_enlace)
        monkeypatch.setattr(cc.os, "readlink", destino_de)
    before = cc.fingerprint(tmp_path)
    (destino / "SKILL.md").write_text("name: github-pelukron-flow\notro\n", encoding="utf-8")
    assert cc.fingerprint(tmp_path) == before
    if real:
        link.unlink()
        link.symlink_to(otro, target_is_directory=True)
    else:
        apuntados[link] = otro
    assert cc.fingerprint(tmp_path) != before


def test_fingerprint_ignora_el_latido_del_gateway(tmp_path):
    """Lock, heartbeats y el sello de jobs.json mutan en cada tick: no son estado (#258).

    Hermes reescribe ``updated_at`` en cada save_jobs y, al cerrar una corrida,
    last_status, claims y repeat.completed. Eso también es latido.
    """
    cron = tmp_path / "cron"
    cron.mkdir()
    jobs = cron / "jobs.json"
    jobs.write_text(
        '{"updated_at":"t0","jobs":[{"name":"a","command":"uv run a","state":"scheduled",'
        '"last_run_at":"t0","next_run_at":"t1","last_status":"ok","last_error":null,'
        '"failure_streak":0,"fire_claim":null,"repeat":{"times":null,"completed":1}}]}',
        encoding="utf-8",
    )
    before = cc.fingerprint(tmp_path)

    (cron / ".tick.lock").write_text("1", encoding="utf-8")
    (cron / "ticker_heartbeat").write_text("hb", encoding="utf-8")
    (cron / "ticker_last_success").write_text("ok", encoding="utf-8")
    (cron / "executions.db").write_bytes(b"db")
    (tmp_path / "gateway_state.json").write_text("{}", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    (state / "gateway.heartbeat").write_text("beat", encoding="utf-8")
    salida = cron / "output" / "e5d16442a694"
    salida.mkdir(parents=True)
    (salida / "2026-09-22_09-30-18.md").write_text("run", encoding="utf-8")
    jobs.write_text(
        '{"updated_at":"t9","jobs":[{"name":"a","command":"uv run a","state":"running",'
        '"last_run_at":"t9","next_run_at":"t8","last_status":"error","last_error":"x",'
        '"failure_streak":2,"fire_claim":{"by":"tick"},"repeat":{"times":null,"completed":2}}]}',
        encoding="utf-8",
    )

    assert cc.fingerprint(tmp_path) == before


def test_fingerprint_ignora_logs(tmp_path):
    """logs/ no es de los jobs: escribir ahí no mueve la huella (#241, #258)."""
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    before = cc.fingerprint(tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "hermes-scripts.log").write_text("ruido", encoding="utf-8")
    assert cc.fingerprint(tmp_path) == before


def test_fingerprint_ignora_sidecars_sqlite(tmp_path):
    """Los -shm/-wal de una DB viva aparecen y desaparecen: no son estado (#241)."""
    (tmp_path / "kanban.db").write_bytes(b"db")
    before = cc.fingerprint(tmp_path)
    for sufijo in ("-shm", "-wal"):
        (tmp_path / f"kanban.db{sufijo}").write_bytes(b"memoria de trabajo")
        assert cc.fingerprint(tmp_path) == before


def test_fingerprint_tolera_archivo_que_desaparece(tmp_path, monkeypatch):
    """Un archivo que se esfuma entre listarlo y leerlo no puede romper el canary (#241)."""
    objetivo = tmp_path / "scripts" / "dato.sh"
    objetivo.parent.mkdir(parents=True)
    objetivo.write_text("#!/bin/sh\n", encoding="utf-8")
    real = Path.read_bytes

    def desaparece(self):
        if self == objetivo:
            self.unlink()
            raise FileNotFoundError(str(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", desaparece)
    huella = cc.fingerprint(tmp_path)
    assert isinstance(huella, str)
    assert len(huella) == 64


def test_sano_stdout_vacio(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cc, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(cc, "run_drift_check", lambda *_a, **_k: None)
    monkeypatch.setattr(cc, "run_entrypoint", lambda *_a, **_k: None)
    monkeypatch.setattr(cc, "send_canary", lambda *_a, **_k: None)
    (tmp_path / "keep.txt").write_text("ok", encoding="utf-8")
    assert cc.main([]) == 0
    assert capsys.readouterr().out == ""


def test_entrypoint_roto_nombra_el_paso(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cc, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(cc, "run_drift_check", lambda *_a, **_k: None)

    def boom(name, *_a, **_k):
        return f"{name} rc=1"

    monkeypatch.setattr(cc, "run_entrypoint", boom)
    assert cc.main([]) == 1
    out = capsys.readouterr().out
    assert "cron-canary:" in out
    assert "rc=1" in out


def test_huella_rota_si_el_sandbox_filtra(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cc, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(cc, "run_drift_check", lambda *_a, **_k: None)

    def muta(_name, _repo, _sandbox):
        scripts = tmp_path / "scripts"
        scripts.mkdir(exist_ok=True)
        (scripts / "leak.sh").write_text("pwn", encoding="utf-8")
        return None

    monkeypatch.setattr(cc, "run_entrypoint", muta)
    monkeypatch.setattr(cc, "send_canary", lambda *_a, **_k: None)
    assert cc.main([]) == 1
    assert "huella" in capsys.readouterr().out


def test_send_exige_message_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")

    def fake_post(_url, _data):
        return {"ok": True, "result": {"message_id": 42}}

    assert cc.send_canary("hola", post=fake_post) is None

    def bad_post(_url, _data):
        return {"ok": False, "description": "fail"}

    assert cc.send_canary("hola", post=bad_post) is not None


def test_send_sin_token_no_hace_nada(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert cc.send_canary("hola", post=lambda *_a: {"ok": True}) is None


def test_manifiesto_declara_cron_canary():
    from src import install_cron as ic

    jobs = ic.parse_jobs(ic.load_manifest(REPO / ic.MANIFEST_DEFAULT))
    canary = next(j for j in jobs if j.name == "cron-canary")
    assert canary.schedule == "30 2 * * *"
    assert canary.is_no_agent
    assert canary.wrapper == "cron-canary.sh"
    assert "src/cron_canary.py" in canary.command


def test_entrypoint_usa_uv_absoluto(tmp_path, monkeypatch):
    """Igual que adopted-sha-audit: en cron `uv` no está en el PATH (#254)."""
    monkeypatch.delenv("UV", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(tmp_path))
    uv = tmp_path / ".hermes" / "bin" / "uv"
    uv.parent.mkdir(parents=True)
    uv.write_text("#!/bin/sh\n", encoding="utf-8")
    uv.chmod(0o755)
    visto: dict[str, list[str]] = {}

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **_kw):
        visto["argv"] = argv
        return _Proc()

    monkeypatch.setattr(cc.subprocess, "run", fake_run)

    assert cc.run_entrypoint("reporte-uso-hermes", tmp_path, tmp_path) is None

    argv = visto["argv"]
    assert Path(argv[0]).is_absolute(), f"{argv[0]} no es absoluto"
    assert Path(argv[0]).exists(), f"{argv[0]} no existe"
    assert argv[1] == "run"
