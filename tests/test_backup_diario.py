"""Tests para backup-diario.py."""

import gzip
import importlib.util
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "backup_diario", SCRIPTS_DIR / "src" / "scripts" / "backup_diario.py"
)
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

        # Changelog independiente del repo: incluye sección [Unreleased] para
        # ejercitar la release note sin depender del estado de CHANGELOG.md.
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "## [Unreleased]\n\n### 🚀 Added\n- Cambio de prueba\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(_mod, "CHANGELOG", changelog)

        _mod.main()
        captured = capsys.readouterr()
        assert "Backup OK" in captured.out
        assert "Ubicación del respaldo:" in captured.out
        assert "state.db dump" in captured.out
        assert "Release note [Unreleased]" in captured.out


class TestBackupConfigNoPesaDeMas:
    """El tarball solo lleva configuracion: los directorios pesados quedan fuera.

    Con el corpus real de ~/.hermes (node 320 MB, backups 302 MB, bin 89 MB,
    retired-wal 110 MB, audits 44 MB, lsp 34 MB) el tarball llegaba a ~965 MB y
    gzip no terminaba en los 600 s del runner de cron: quedaba truncado.
    """

    PESADOS = ("node", "backups", "bin", "lsp", "lazy-target", "audits", ".curator_backups")

    def test_excluye_directorios_pesados_y_artefactos(self, tmp_path):
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        (hermes_dir / "skills").mkdir()
        (hermes_dir / "skills" / "keep.md").write_text("skill content")
        for pesado in self.PESADOS:
            (hermes_dir / pesado).mkdir()
            (hermes_dir / pesado / "pesado.bin").write_text("x")
        (hermes_dir / "models_dev_cache.json").write_text("{}")
        retired = hermes_dir / "state.db.retired-wal-20260916-000000-1"
        retired.mkdir()
        (retired / "state.db").write_text("sqlite")
        (hermes_dir / "state.db.auto-maintenance.lock").write_text("")

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        result = _mod.backup_config(hermes_dir, backup_dir, "2026-09-16")

        with tarfile.open(result, "r:gz") as tar:
            names = tar.getnames()

        assert ".hermes/skills/keep.md" in names
        for pesado in self.PESADOS:
            assert f".hermes/{pesado}/pesado.bin" not in names, f"{pesado} sigue dentro del tarball"
        assert ".hermes/models_dev_cache.json" not in names
        assert ".hermes/state.db.auto-maintenance.lock" not in names
        assert not [n for n in names if n.startswith(".hermes/state.db.retired-wal-")]


class TestVerifyArtifacts:
    """Un respaldo truncado no puede pasar por bueno."""

    def test_detecta_tarball_truncado(self, tmp_path):
        good = tmp_path / "hermes_2026-09-16.tar.gz"
        payload = tmp_path / "payload.bin"
        payload.write_bytes(b"x" * 3_000_000)
        with tarfile.open(good, "w:gz") as tar:
            tar.add(payload, arcname="payload.bin")
        assert _mod.verify_artifacts([good]) == []

        data = good.read_bytes()
        good.write_bytes(data[: len(data) // 2])
        assert _mod.verify_artifacts([good]) == [good]

    def test_detecta_dump_truncado(self, tmp_path):
        path = tmp_path / "state_2026-09-16.sql.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            for i in range(20000):
                fh.write(f"INSERT INTO t VALUES ({i});\n")
        assert _mod.verify_artifacts([path]) == []

        data = path.read_bytes()
        path.write_bytes(data[: len(data) // 2])
        assert _mod.verify_artifacts([path]) == [path]

    def test_ignora_none(self, tmp_path):
        assert _mod.verify_artifacts([None]) == []


class TestMainIntegridad:
    """main() devuelve codigo != 0 si un artefacto quedo corrupto."""

    def _preparar(self, tmp_path, monkeypatch):
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        backup_dir = hermes_dir / "backup" / "daily"
        backup_dir.mkdir(parents=True)
        db_path = hermes_dir / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("## [Unreleased]\n", encoding="utf-8")
        monkeypatch.setattr(_mod, "HERMES", hermes_dir)
        monkeypatch.setattr(_mod, "BACKUP_DIR", backup_dir)
        monkeypatch.setattr(_mod, "STATE_DB", db_path)
        monkeypatch.setattr(_mod, "CHANGELOG", changelog)
        return hermes_dir, backup_dir

    def test_devuelve_1_si_el_tarball_esta_truncado(self, tmp_path, monkeypatch, capsys):
        hermes_dir, backup_dir = self._preparar(tmp_path, monkeypatch)

        def backup_config_truncado(hermes_dir, backup_dir, date_str, *args, **kwargs):
            path = backup_dir / f"hermes_{date_str}.tar.gz"
            payload = hermes_dir / "payload.bin"
            payload.write_bytes(b"y" * 3_000_000)
            with tarfile.open(path, "w:gz") as tar:
                tar.add(payload, arcname="payload.bin")
            data = path.read_bytes()
            path.write_bytes(data[: len(data) // 2])
            return path

        monkeypatch.setattr(_mod, "backup_config", backup_config_truncado)

        assert _mod.main() == 1
        captured = capsys.readouterr()
        assert "Backup OK" not in captured.out
        assert "corrupto" in captured.out or "corrupto" in captured.err

    def test_devuelve_0_cuando_todo_esta_bien(self, tmp_path, monkeypatch, capsys):
        self._preparar(tmp_path, monkeypatch)
        assert _mod.main() == 0
        assert "Backup OK" in capsys.readouterr().out
