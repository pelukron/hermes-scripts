#!/usr/bin/env python3
"""Hermes backup diario — local, rotación 7 días. 0 dependencias externas."""

import gzip
import logging
import sqlite3
import tarfile
import time
from datetime import datetime
from pathlib import Path

from hermes_common import repo_root, setup_logging, version_footer

log = logging.getLogger("hermes")

HOME = Path.home()
HERMES = HOME / ".hermes"
BACKUP_DIR = HERMES / "backup" / "daily"
STATE_DB = HERMES / "state.db"
RETENTION_DAYS = 7
# Raíz del repo, no src/scripts/ (#207): el CHANGELOG vive en la raíz.
CHANGELOG = repo_root() / "CHANGELOG.md"

# Elementos de ~/.hermes que no son configuracion y dominan el tamano del
# tarball. Medido el 2026-09-16 en el host: node 320 MB, backups 302 MB,
# bin 89 MB, state.db.retired-wal-* 154 MB, audits 44 MB, lsp 34 MB. Con ellos
# dentro el tarball llegaba a ~965 MB y gzip no terminaba en los 600 s del
# runner de cron: el archivo quedaba truncado y el job salia en error (#144).
EXCLUDED_NAMES = frozenset(
    {
        "state.db",
        "state.db-shm",
        "state.db-wal",
        "cache",
        "venv",
        "backup",
        "state-snapshots",
        "logs",
        "node",
        "backups",
        "bin",
        "lsp",
        "lazy-target",
        "audits",
        ".curator_backups",
        "models_dev_cache.json",
    }
)
EXCLUDED_PREFIXES = ("state.db.retired-wal-",)
EXCLUDED_SUFFIXES = (".lock",)
MAX_TAR_BYTES = 200 * 1024 * 1024


def is_excluded(name):
    """True si el elemento de ~/.hermes no es configuracion y no se respalda.

    Args:
        name: Nombre del elemento en el primer nivel de ~/.hermes.

    Returns:
        bool: True si debe quedar fuera del tarball.
    """
    return (
        name in EXCLUDED_NAMES
        or name.startswith(EXCLUDED_PREFIXES)
        or name.endswith(EXCLUDED_SUFFIXES)
    )


def verify_artifacts(paths):
    """Verifica que cada artefacto se pueda leer completo.

    Args:
        paths: Iterable de rutas (o None) generadas por el backup.

    Returns:
        list: rutas corruptas (truncadas o ilegibles); vacia si todo esta bien.
    """
    corrupt = []
    for path in paths:
        if path is None:
            continue
        try:
            if str(path).endswith(".tar.gz"):
                with tarfile.open(path, "r:gz") as tar:
                    for _ in tar:
                        pass
            else:
                with gzip.open(path, "rb") as handle:
                    while handle.read(1 << 20):
                        pass
        except Exception as exc:
            log.error(f"✗ {path.name} corrupto: {exc}")
            corrupt.append(path)
    return corrupt


def dump_sqlite(state_db, backup_dir, date_str):
    """Create a gzip-compressed SQLite dump of state.db.

    Args:
        state_db: Path to the SQLite database file.
        backup_dir: Directory to store the dump.
        date_str: Date string (YYYY-MM-DD) for filename.

    Returns:
        Path or None: Path to the created dump file, or None on failure.
    """
    if not state_db.exists():
        log.warning("state.db no encontrado, omitiendo dump SQL.")
        return None

    dump_path = backup_dir / f"state_{date_str}.sql.gz"
    try:
        conn = sqlite3.connect(str(state_db))
        try:
            # Streaming: state.db ya pasa de 60 MB y materializar el dump
            # completo (lista + join) costaba ~100 MB de pico en RAM.
            with gzip.open(dump_path, "wt", encoding="utf-8") as f:
                for statement in conn.iterdump():
                    f.write(statement)
                    f.write("\n")
        finally:
            conn.close()
        log.info(f"✓ state.db dump → {dump_path} ({dump_path.stat().st_size} bytes)")
        return dump_path
    except Exception as e:
        log.error(f"✗ state.db dump ERROR: {e}")
        return None


def backup_config(hermes_dir, backup_dir, date_str):
    """Create a tar.gz of Hermes config (skills, scripts, cron, memories).

    Args:
        hermes_dir: Path to the .hermes directory.
        backup_dir: Directory to store the tarball.
        date_str: Date string (YYYY-MM-DD) for filename.

    Returns:
        Path: Path to the created tarball.
    """
    tar_path = backup_dir / f"hermes_{date_str}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for item in sorted(hermes_dir.iterdir()):
            if is_excluded(item.name):
                continue
            tar.add(item, arcname=f".hermes/{item.name}")
    log.info(f"✓ hermes config → {tar_path} ({tar_path.stat().st_size} bytes)")
    return tar_path


def cleanup_bak_files(hermes_dir, retention_days=3):
    """Delete .bak files older than retention_days.

    Args:
        hermes_dir: Path to the .hermes directory.
        retention_days: Maximum age in days for .bak files. Defaults to 3.

    Returns:
        int: Number of .bak files deleted.
    """
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for f in hermes_dir.rglob("*.bak"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    log.info(f"✓ .bak cleanup: {deleted} borrados (> {retention_days}d)")
    return deleted


def rotate_backups(backup_dir, retention_days=7):
    """Delete backup files (*.gz) older than retention_days.

    Args:
        backup_dir: Directory containing backup files.
        retention_days: Maximum age in days for backups. Defaults to 7.

    Returns:
        tuple: (deleted_count, remaining_count).
    """
    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    for f in backup_dir.glob("*.gz"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    remaining = len(list(backup_dir.glob("*.gz")))
    log.info(f"✓ rotación: {deleted} borrados, {remaining} retenidos")
    return deleted, remaining


def release_note_unreleased(changelog_path):
    """Extract the [Unreleased] section of a Keep-a-Changelog file.

    Args:
        changelog_path: Path to CHANGELOG.md.

    Returns:
        str or None: The markdown body of the [Unreleased] section
            (without the header line), or None if absent/empty.
    """
    if not changelog_path.exists():
        return None
    lines = changelog_path.read_text(encoding="utf-8").splitlines()
    in_unreleased = False
    body = []
    for ln in lines:
        if ln.startswith("## [Unreleased]"):
            in_unreleased = True
            continue
        if in_unreleased and ln.startswith("## "):
            break
        if in_unreleased:
            body.append(ln)
    while body and not body[-1].strip():
        body.pop()
    while body and not body[0].strip():
        body.pop(0)
    return "\n".join(body) if any(ln.strip() for ln in body) else None


def main():
    """Run daily backup: SQL dump, config tarball, bak cleanup, rotation.

    Returns:
        int: 0 si ambos artefactos se verifican; 1 si alguno quedo corrupto.
    """
    setup_logging()
    date_str = datetime.now().strftime("%Y-%m-%d")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    dump = dump_sqlite(STATE_DB, BACKUP_DIR, date_str)
    tarball = backup_config(HERMES, BACKUP_DIR, date_str)
    cleanup_bak_files(HERMES)
    rotate_backups(BACKUP_DIR)

    corrupt = verify_artifacts([dump, tarball])
    if corrupt:
        log.error(
            "✗ Respaldo invalido, no se reporta como OK: "
            + ", ".join(path.name for path in corrupt)
        )
        return 1

    if tarball.stat().st_size > MAX_TAR_BYTES:
        log.warning(f"⚠️ tarball de {tarball.stat().st_size} bytes: revisar exclusiones")

    output = []
    output.append(f"**📦 Backup OK — {date_str}**")
    output.append("")
    output.append(f"**Ubicación del respaldo:** `{BACKUP_DIR}`")
    output.append("")
    output.append(version_footer())
    output.append("")

    release_note = release_note_unreleased(CHANGELOG)
    if release_note:
        output.append("**📝 Release note [Unreleased]:**")
        output.append("")
        output.append("```")
        output.append(release_note)
        output.append("```")

    log.info("\n".join(output))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
