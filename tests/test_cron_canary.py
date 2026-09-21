"""cron-canary (#218): sandbox, huella, silencio en verde, 1 mensaje."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

import cron_canary as cc  # noqa: E402


def test_allow_y_deny_no_se_solapan():
    assert not set(cc.ALLOW_LIST) & set(cc.DENY_LIST)
    assert "monitor-ram-mexico" in cc.ALLOW_LIST
    assert "backup-diario" in cc.DENY_LIST


def test_payload_cabe_en_un_mensaje():
    text = cc.canary_payload()
    assert 0 < cc.utf16_len(text) <= cc.TELEGRAM_UTF16_LIMIT


def test_fingerprint_cambia_si_escribe(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    before = cc.fingerprint(tmp_path)
    (tmp_path / "a.json").write_text('{"x": 1}', encoding="utf-8")
    assert cc.fingerprint(tmp_path) != before


def test_fingerprint_ignora_logs(tmp_path):
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
    objetivo = tmp_path / "dato.json"
    objetivo.write_text("{}", encoding="utf-8")
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
        (tmp_path / "leak.json").write_text("pwn", encoding="utf-8")
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
