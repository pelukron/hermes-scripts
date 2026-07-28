#!/usr/bin/env python3
"""Cleanup housekeeping: backups, caches, stores. Keep 3 newest backups."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
BACKUP_DIR = HOME / ".hermes" / "backup" / "daily"
KEEP = 3


def log(msg: str):
    print(f"[cleanup] {msg}")


def clean_backups():
    """Keep only the KEEP newest backups."""
    if not BACKUP_DIR.exists():
        log(f"backup dir not found: {BACKUP_DIR}")
        return

    files = sorted(BACKUP_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    to_delete = files[KEEP:]

    if not to_delete:
        log("no old backups to clean")
        return

    deleted = 0
    deleted_size = 0
    for f in to_delete:
        sz = f.stat().st_size
        f.unlink()
        deleted += 1
        deleted_size += sz

    log(f"deleted {deleted} old backup files ({deleted_size / 1024 / 1024:.0f} MB)")


def run_cmd(cmd: list[str], desc: str):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            log(f"{desc}: ok")
            return True
        else:
            log(f"{desc}: error (exit {result.returncode})")
            log(f"  stderr: {result.stderr.strip()[:200]}")
            return False
    except Exception as e:
        log(f"{desc}: exception: {e}")
        return False


def main():
    log("=== cleanup start ===")

    # 1. Backups
    clean_backups()

    # 2. npm cache
    run_cmd(["npm", "cache", "clean", "--force"], "npm cache")

    # 3. pnpm store
    run_cmd(["pnpm", "store", "prune"], "pnpm store")

    # 4. pip cache
    run_cmd([sys.executable, "-m", "pip", "cache", "purge"], "pip cache")

    log("=== cleanup done ===")


if __name__ == "__main__":
    main()