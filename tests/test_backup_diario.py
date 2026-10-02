"""Tests para backup-diario.py."""

import gzip
import importlib.util
import shutil
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

import pytest

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

    Medido el 2026-09-28 (#388): el update semanal reinstalo tools/ (1.67 GB:
    ffmpeg, python, chromium, node, uv, tirith, npm, ripgrep) e installs/ (851 MB)
    y el tarball volvio a truncarse dos noches. PESADOS es la lista medida del
    host, no una copia parcial de EXCLUDED_NAMES.
    """

    PESADOS = (
        "node",
        "tools",
        "installs",
        "backups",
        "bin",
        "lsp",
        "lazy-target",
        "audits",
        ".curator_backups",
    )

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


class TestChangelogPath:
    """Regresión #207: CHANGELOG apuntaba a src/scripts/CHANGELOG.md (inexistente),
    así que release_note_unreleased() devolvía None en silencio y el reporte de
    backup nunca mostraba la nota de release."""

    def test_changelog_es_el_del_repo(self):
        assert _mod.CHANGELOG.is_file(), _mod.CHANGELOG
        assert _mod.CHANGELOG.parent == _mod.repo_root()
        assert "## [Unreleased]" in _mod.CHANGELOG.read_text(encoding="utf-8")


class TestBackupConfigSymlinks:
    """Las skills enlazadas viajan como enlaces, no como contenido (#260).

    `backup_config` usa `tar.add` sin `dereference`: el tar guarda el enlace.
    Por eso la restauración exige primero el clon y después `~/.hermes`
    (ver "Restaurar un backup" en docs/INSTALL.md).
    """

    def _linked_hermes(self, tmp_path):
        """Clon falso + `.hermes` falso con un enlace como los del despliegue."""
        clone_skill = tmp_path / "fake-clon" / "skills" / "github-pelukron-flow"
        clone_skill.mkdir(parents=True)
        (clone_skill / "SKILL.md").write_text(
            "---\nname: github-pelukron-flow\n---\n", encoding="utf-8"
        )
        hermes_dir = tmp_path / ".hermes"
        link = hermes_dir / "skills" / "github" / "github-pelukron-flow"
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(clone_skill, target_is_directory=True)
        except OSError:
            pytest.skip("crear symlinks exige privilegio en este sistema")
        return hermes_dir, clone_skill, link

    def test_guarda_enlaces_como_enlaces(self, tmp_path):
        hermes_dir, clone_skill, _link = self._linked_hermes(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        result = _mod.backup_config(hermes_dir, backup_dir, "2026-09-25")

        with tarfile.open(result, "r:gz") as tar:
            names = tar.getnames()
            member = tar.getmember(".hermes/skills/github/github-pelukron-flow")

        assert member.issym()
        assert member.linkname == str(clone_skill)
        assert ".hermes/skills/github/github-pelukron-flow/SKILL.md" not in names

    def test_restaurado_sin_clon_cuelga_y_con_clon_resuelve(self, tmp_path):
        hermes_dir, clone_skill, _link = self._linked_hermes(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        result = _mod.backup_config(hermes_dir, backup_dir, "2026-09-25")

        # Sin el clon en su ruta: el escenario de restaurar solo `~/.hermes`.
        shutil.rmtree(tmp_path / "fake-clon")
        restore = tmp_path / "restore"
        restore.mkdir()
        with tarfile.open(result, "r:gz") as tar:
            try:
                # fully_trusted: la restauración es `tar -xzf` del operador sobre
                # su propio backup; `data` rechazaría estos enlaces porque el
                # destino absoluto vive fuera del directorio de extracción.
                tar.extractall(restore, filter="fully_trusted")
            except OSError:
                pytest.skip("extraer symlinks exige privilegio en este sistema")
        restored = restore / ".hermes" / "skills" / "github" / "github-pelukron-flow"
        assert restored.is_symlink()
        assert not restored.exists()

        # Con el clon primero (el orden que documenta INSTALL.md), resuelve.
        clone_skill.mkdir(parents=True)
        (clone_skill / "SKILL.md").write_text(
            "---\nname: github-pelukron-flow\n---\n", encoding="utf-8"
        )
        assert restored.exists()
        assert "github-pelukron-flow" in restored.joinpath("SKILL.md").read_text(encoding="utf-8")


class TestEscrituraAtomica:
    """Un kill a mitad de escritura no puede dejar el nombre definitivo (#397).

    El runner del cron mata el proceso a los 600 s. Con el archivo abierto sobre su
    ruta final, el tarball y el dump quedaban truncados **con su nombre definitivo** y
    la rotacion los retenia como respaldos validos (medido el 2026-09-27 y 28).
    """

    def _hermes_minimo(self, tmp_path):
        hermes_dir = tmp_path / ".hermes"
        hermes_dir.mkdir()
        (hermes_dir / "skills").mkdir()
        (hermes_dir / "skills" / "keep.md").write_text("skill content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        return hermes_dir, backup_dir

    def _state_db(self, tmp_path):
        db_path = tmp_path / "state.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        return db_path

    def test_tarball_escribe_en_part_y_renombra_al_cerrar(self, tmp_path, monkeypatch):
        hermes_dir, backup_dir = self._hermes_minimo(tmp_path)
        final = backup_dir / "hermes_2026-09-29.tar.gz"
        abiertos = []
        real_open = _mod.tarfile.open

        def espia(path, *args, **kwargs):
            abiertos.append(Path(path))
            assert not final.exists(), "el nombre definitivo existe antes de cerrar el tarball"
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(_mod.tarfile, "open", espia)
        result = _mod.backup_config(hermes_dir, backup_dir, "2026-09-29")

        assert abiertos and abiertos[0].name.endswith(_mod.PART_SUFFIX)
        assert result == final
        assert result.is_file()
        # El espia sigue puesto: se restaura antes de leer el tarball ya renombrado.
        monkeypatch.setattr(_mod.tarfile, "open", real_open)
        with tarfile.open(result, "r:gz") as tar:
            assert ".hermes/skills/keep.md" in tar.getnames()
        assert list(backup_dir.glob(f"*{_mod.PART_SUFFIX}")) == []

    def test_dump_escribe_en_part_y_renombra_al_cerrar(self, tmp_path, monkeypatch):
        db_path = self._state_db(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        final = backup_dir / "state_2026-09-29.sql.gz"
        abiertos = []
        real_open = _mod.gzip.open

        def espia(path, *args, **kwargs):
            abiertos.append(Path(path))
            assert not final.exists(), "el nombre definitivo existe antes de cerrar el dump"
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(_mod.gzip, "open", espia)
        result = _mod.dump_sqlite(db_path, backup_dir, "2026-09-29")

        assert abiertos and abiertos[0].name.endswith(_mod.PART_SUFFIX)
        assert result == final
        assert result.is_file()
        assert list(backup_dir.glob(f"*{_mod.PART_SUFFIX}")) == []

    def test_tarball_no_deja_nada_si_la_escritura_muere(self, tmp_path, monkeypatch):
        hermes_dir, backup_dir = self._hermes_minimo(tmp_path)

        def revienta(path, *args, **kwargs):
            Path(path).write_bytes(b"basura incompleta")
            raise RuntimeError("kill simulado")

        monkeypatch.setattr(_mod.tarfile, "open", revienta)
        with pytest.raises(RuntimeError):
            _mod.backup_config(hermes_dir, backup_dir, "2026-09-29")

        assert not (backup_dir / "hermes_2026-09-29.tar.gz").exists()
        assert list(backup_dir.glob(f"*{_mod.PART_SUFFIX}")) == []

    def test_dump_no_deja_nada_si_la_escritura_muere(self, tmp_path, monkeypatch):
        db_path = self._state_db(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        def revienta(path, *args, **kwargs):
            Path(path).write_text("parcial")
            raise RuntimeError("kill simulado")

        monkeypatch.setattr(_mod.gzip, "open", revienta)
        assert _mod.dump_sqlite(db_path, backup_dir, "2026-09-29") is None

        assert not (backup_dir / "state_2026-09-29.sql.gz").exists()
        assert list(backup_dir.glob(f"*{_mod.PART_SUFFIX}")) == []


class TestPartHuerfanos:
    """Los `.part` de una corrida muerta se limpian y no cuentan como respaldo (#397)."""

    def test_borra_los_viejos_y_deja_los_nuevos(self, tmp_path):
        import os as os_module

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        viejo = backup_dir / "state_2026-09-28.sql.gz.part"
        viejo.write_text("parcial")
        nuevo = backup_dir / "state_2026-09-29.sql.gz.part"
        nuevo.write_text("parcial")
        old_time = time.time() - (2 * 3600)
        os_module.utime(str(viejo), (old_time, old_time))

        assert _mod.cleanup_part_files(backup_dir, max_age_seconds=3600) == 1
        assert not viejo.exists()
        assert nuevo.exists()

    def test_rotate_no_borra_ni_cuenta_los_part(self, tmp_path):
        import os as os_module

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        valido = backup_dir / "hermes_2026-09-29.tar.gz"
        valido.write_bytes(b"x")
        part_viejo = backup_dir / "hermes_2026-09-27.tar.gz.part"
        part_viejo.write_bytes(b"y")
        old_time = time.time() - (10 * 86400)
        os_module.utime(str(part_viejo), (old_time, old_time))

        deleted, remaining = _mod.rotate_backups(backup_dir, retention_days=7)

        assert deleted == 0
        # El `.part` no cuenta como respaldo retenido ni lo borra la rotacion:
        # de el se encarga cleanup_part_files().
        assert remaining == 1
        assert part_viejo.exists()
        assert _mod.cleanup_part_files(backup_dir, max_age_seconds=3600) == 1
        assert not part_viejo.exists()

    def test_main_limpia_los_part_huerfanos(self, tmp_path, monkeypatch, capsys):
        import os as os_module

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

        huerfano = backup_dir / "state_2026-09-28.sql.gz.part"
        huerfano.write_text("parcial")
        old_time = time.time() - (3 * 3600)
        os_module.utime(str(huerfano), (old_time, old_time))

        monkeypatch.setattr(_mod, "HERMES", hermes_dir)
        monkeypatch.setattr(_mod, "BACKUP_DIR", backup_dir)
        monkeypatch.setattr(_mod, "STATE_DB", db_path)
        monkeypatch.setattr(_mod, "CHANGELOG", changelog)

        assert _mod.main() == 0
        assert not huerfano.exists()
        assert "Backup OK" in capsys.readouterr().out
