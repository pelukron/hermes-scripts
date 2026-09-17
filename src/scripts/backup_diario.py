#!/usr/bin/env python3
"""Hermes backup diario — local, rotación 7 días. 0 dependencias externas."""

import gzip
import sqlite3
import tarfile
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
HERMES = HOME / ".hermes"
BACKUP_DIR = HERMES / "backup" / "daily"
STATE_DB = HERMES / "state.db"
RETENTION_DAYS = 7
SCRIPT_DIR = Path(__file__).resolve().parent
CHANGELOG = SCRIPT_DIR / "CHANGELOG.md"


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
        print("state.db no encontrado, omitiendo dump SQL.")
        return None

    dump_path = backup_dir / f"state_{date_str}.sql.gz"
    try:
        conn = sqlite3.connect(str(state_db))
        dump = "\n".join(conn.iterdump())
        conn.close()
        with gzip.open(dump_path, "wt", encoding="utf-8") as f:
            f.write(dump)
        print(f"✓ state.db dump → {dump_path} ({dump_path.stat().st_size} bytes)")
        return dump_path
    except Exception as e:
        print(f"✗ state.db dump ERROR: {e}")
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
    excluded = {
        "state.db",
        "state.db-shm",
        "state.db-wal",
        "cache",
        "venv",
        "backup",
        "state-snapshots",
        "logs",
    }
    tar_path = backup_dir / f"hermes_{date_str}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for item in sorted(hermes_dir.iterdir()):
            if item.name in excluded:
                continue
            tar.add(item, arcname=f".hermes/{item.name}")
    print(f"✓ hermes config → {tar_path} ({tar_path.stat().st_size} bytes)")
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
    print(f"✓ .bak cleanup: {deleted} borrados (> {retention_days}d)")
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
    print(f"✓ rotación: {deleted} borrados, {remaining} retenidos")
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
    """Run daily backup: SQL dump, config tarball, bak cleanup, rotation."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    dump_sqlite(STATE_DB, BACKUP_DIR, date_str)
    backup_config(HERMES, BACKUP_DIR, date_str)
    cleanup_bak_files(HERMES)
    rotate_backups(BACKUP_DIR)

    output = []
    output.append(f"**📦 Backup OK — {date_str}**")
    output.append("")
    output.append(f"**Ubicación del respaldo:** `{BACKUP_DIR}`")
    output.append("")

    release_note = release_note_unreleased(CHANGELOG)
    if release_note:
        output.append("**📝 Release note [Unreleased]:**")
        output.append("")
        output.append("```")
        output.append(release_note)
        output.append("```")

    print("\n".join(output))


if __name__ == "__main__":
    main()
