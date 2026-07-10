#!/usr/bin/env python3
"""Hermes backup diario — local, rotación 7 días. 0 dependencias externas."""

import sqlite3, tarfile, gzip, os, glob, time
from pathlib import Path
from datetime import datetime

HOME = Path.home()
HERMES = HOME / ".hermes"
BACKUP_DIR = HERMES / "backup" / "daily"
STATE_DB = HERMES / "state.db"
RETENTION_DAYS = 7
DATE = datetime.now().strftime("%Y-%m-%d")

BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 1. SQLite dump comprimido
if STATE_DB.exists():
    dump_path = BACKUP_DIR / f"state_{DATE}.sql.gz"
    try:
        conn = sqlite3.connect(str(STATE_DB))
        dump = "\n".join(conn.iterdump())
        conn.close()
        with gzip.open(dump_path, "wt", encoding="utf-8") as f:
            f.write(dump)
        print(f"✓ state.db dump: {dump_path.stat().st_size} bytes")
    except Exception as e:
        print(f"✗ state.db dump ERROR: {e}")

# 2. Config + skills + scripts + cron + memories (tar.gz)
tar_path = BACKUP_DIR / f"hermes_{DATE}.tar.gz"
with tarfile.open(tar_path, "w:gz") as tar:
    for item in sorted(HERMES.iterdir()):
        name = item.name
        if name in (
            "state.db",
            "state.db-shm",
            "state.db-wal",
            "cache",
            "venv",
            "backup",
            "state-snapshots",
            "logs",
        ):
            continue
        tar.add(item, arcname=f".hermes/{name}")
print(f"✓ hermes config: {tar_path.stat().st_size} bytes")

# 3. Limpiar backups manuales (.bak) > 3 días
BAK_RETENTION = 3
bak_cutoff = time.time() - (BAK_RETENTION * 86400)
bak_deleted = 0
for f in HERMES.rglob("*.bak"):
    if f.stat().st_mtime < bak_cutoff:
        f.unlink()
        bak_deleted += 1
print(f"✓ .bak cleanup: {bak_deleted} borrados (> {BAK_RETENTION}d)")

# 4. Rotación: borrar > 7 días
cutoff = time.time() - (RETENTION_DAYS * 86400)
deleted = 0
for f in BACKUP_DIR.glob("*.gz"):
    if f.stat().st_mtime < cutoff:
        f.unlink()
        deleted += 1
remaining = len(list(BACKUP_DIR.glob("*.gz")))
print(f"✓ rotación: {deleted} borrados, {remaining} retenidos")
print(f"backup OK — {DATE}")
