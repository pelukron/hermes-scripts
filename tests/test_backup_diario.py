"""Tests para backup-diario.py."""

import gzip
import importlib.util
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("backup_diario", SCRIPTS_DIR / "backup-diario.py")
_mod = importlib.util.module_from_spec(spec)
sys.modules["backup_diario"] = _mod
spec.loader.exec_module(_mod)


class TestDumpSqlite:
    """Tests for dump_sqlite()."""

    def test_dump_creates_gz_file(self, tmp_path):
        db_path = tmp_path / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        conn.commit()
        conn.close()

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        result = _mod.dump_sqlite(db_path, backup_dir, "2025-01-01")

        assert result is not None
        assert result.exists()
        assert result.suffix == ".gz"
        assert result.stat().st_size > 0

        with gzip.open(result, "rt", encoding="utf-8") as f:
            content = f.read()
        assert "test" in content
        assert "INSERT" in content

    def test_dump_missing_db_returns_none(self, tmp_path):
        fake_db = tmp_path / "nonexistent.db"
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        result = _mod.dump_sqlite(fake_db, backup_dir, "2025-01-01")
        assert result is None


class TestBackupConfig:
    """Tests for backup_config()."""

    def test_creates_tarball_excluding(self, tmp_path):
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        (hermes_dir / "skills").mkdir()
        (hermes_dir / "skills" / "test.md").write_text("skill content")
        (hermes_dir / "config.yaml").write_text("config: true")
        (hermes_dir / "state.db").write_text("fake db")
        (hermes_dir / "cache").mkdir()
        (hermes_dir / "venv").mkdir()
        (hermes_dir / "backup").mkdir()
        (hermes_dir / "logs").mkdir()

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        result = _mod.backup_config(hermes_dir, backup_dir, "2025-01-01")

        assert result.exists()
        assert result.stat().st_size > 0

        with tarfile.open(result, "r:gz") as tar:
            names = tar.getnames()
        assert ".hermes/skills/test.md" in names
        assert ".hermes/config.yaml" in names
        assert ".hermes/state.db" not in names
        assert ".hermes/cache" not in names
        assert ".hermes/venv" not in names
        assert ".hermes/backup" not in names
        assert ".hermes/logs" not in names


class TestCleanupBakFiles:
    """Tests for cleanup_bak_files()."""

    def test_deletes_old_bak_files(self, tmp_path):
        import os as os_module

        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        sub = hermes_dir / "subdir"
        sub.mkdir()

        fresh = sub / "fresh.bak"
        fresh.write_text("fresh")
        old = sub / "old.bak"
        old.write_text("old")
        old_time = time.time() - (4 * 86400)
        os_module.utime(str(old), (old_time, old_time))

        deleted = _mod.cleanup_bak_files(hermes_dir, retention_days=3)
        assert deleted >= 1
        assert not old.exists()
        assert fresh.exists()

    def test_no_bak_files(self, tmp_path):
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        deleted = _mod.cleanup_bak_files(hermes_dir)
        assert deleted == 0


class TestRotateBackups:
    """Tests for rotate_backups()."""

    def test_deletes_old_gz_files(self, tmp_path):
        import os as os_module

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        fresh = backup_dir / "fresh.gz"
        fresh.write_text("fresh")
        old = backup_dir / "old.gz"
        old.write_text("old")
        old_time = time.time() - (10 * 86400)
        os_module.utime(str(old), (old_time, old_time))

        deleted, remaining = _mod.rotate_backups(backup_dir, retention_days=7)
        assert deleted >= 1
        assert remaining >= 1
        assert not old.exists()
        assert fresh.exists()

    def test_empty_backup_dir(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        deleted, remaining = _mod.rotate_backups(backup_dir)
        assert deleted == 0
        assert remaining == 0


class TestMainSmoke:
    """Smoke test for main()."""

    def test_main_runs_without_error(self, tmp_path, monkeypatch, capsys):
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        backup_dir = hermes_dir / "backup" / "daily"
        backup_dir.mkdir(parents=True)

        db_path = hermes_dir / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        monkeypatch.setattr(_mod, "HERMES", hermes_dir)
        monkeypatch.setattr(_mod, "BACKUP_DIR", backup_dir)
        monkeypatch.setattr(_mod, "STATE_DB", db_path)

        _mod.main()
        captured = capsys.readouterr()
        assert "backup OK" in captured.out
        assert "state.db dump" in captured.out
