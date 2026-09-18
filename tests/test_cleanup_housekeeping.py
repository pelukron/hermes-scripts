"""Tests para cleanup_housekeeping (tmp_path, sin tocar HOME real)."""

import importlib.util
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location(
    "cleanup_housekeeping",
    os.path.join(SCRIPT_DIR, "src", "scripts", "cleanup_housekeeping.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _touch(path, mtime):
    path.write_bytes(b"x" * 10)
    os.utime(path, (mtime, mtime))


class TestCleanBackups:
    def test_keep_3_nuevos(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path)
        ahora = time.time()
        for i in range(5):
            _touch(tmp_path / f"backup-{i}.db", ahora - i * 100)
        mod.clean_backups()
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "backup-0.db",
            "backup-1.db",
            "backup-2.db",
        ]

    def test_menos_de_keep(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path)
        _touch(tmp_path / "only.db", time.time())
        mod.clean_backups()
        assert (tmp_path / "only.db").exists()

    def test_dir_inexistente(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path / "no-existe")
        mod.clean_backups()  # no debe lanzar


class TestCleanOldNews:
    def _news(self, tmp_path, monkeypatch, payload):
        nf = tmp_path / "news_history.json"
        nf.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(mod, "NEWS_FILES", [nf])
        return nf

    def test_purga_viejas(self, tmp_path, monkeypatch):
        ahora = time.time()
        nf = self._news(
            tmp_path,
            monkeypatch,
            {"nueva": ahora, "vieja": ahora - 10 * 86400},
        )
        mod.clean_old_news()
        assert json.loads(nf.read_text(encoding="utf-8")) == {"nueva": ahora}

    def test_sin_purga(self, tmp_path, monkeypatch):
        ahora = time.time()
        nf = self._news(tmp_path, monkeypatch, {"nueva": ahora})
        mod.clean_old_news()
        assert json.loads(nf.read_text(encoding="utf-8")) == {"nueva": ahora}

    def test_json_roto_y_no_dict(self, tmp_path, monkeypatch):
        nf = tmp_path / "news_history.json"
        nf.write_text("no-json{{{", encoding="utf-8")
        monkeypatch.setattr(mod, "NEWS_FILES", [nf])
        mod.clean_old_news()  # no debe lanzar
        nf.write_text("[1,2]", encoding="utf-8")
        mod.clean_old_news()  # no debe lanzar

    def test_archivo_inexistente(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "NEWS_FILES", [tmp_path / "no.json"])
        mod.clean_old_news()  # no debe lanzar


class TestRunCmd:
    def test_ok(self):
        assert mod.run_cmd([sys.executable, "-c", "pass"], "py-ok") is True

    def test_exit_distinto(self):
        assert mod.run_cmd([sys.executable, "-c", "raise SystemExit(3)"], "py-fail") is False

    def test_comando_inexistente(self):
        assert mod.run_cmd(["no-existe-este-bin-xyz"], "missing") is False


class TestMain:
    def test_main_orquesta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(mod, "NEWS_FILES", [])
        llamadas = []
        monkeypatch.setattr(mod, "run_cmd", lambda cmd, desc: llamadas.append(desc) or True)
        mod.main()
        assert llamadas == ["npm cache", "pnpm store", "pip cache"]
