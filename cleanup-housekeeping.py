#!/usr/bin/env python3
"""Cleanup housekeeping: backups, caches, stores, old news. Keep 3 newest backups, news >4d."""

import json
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
BACKUP_DIR = HOME / ".hermes" / "backup" / "daily"
KEEP = 3
NEWS_FILES = [
    HOME / ".hermes" / "data" / "news_history.json",
    HOME / ".hermes" / "data" / "news_history_v2.json",
]
NEWS_MAX_AGE_DAYS = 4


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


def clean_old_news():
    """Remove news entries older than NEWS_MAX_AGE_DAYS."""
    cutoff = time.time() - (NEWS_MAX_AGE_DAYS * 86400)
    total_purged = 0

    for nf in NEWS_FILES:
        if not nf.exists():
            log(f"news file not found: {nf}")
            continue

        try:
            with open(nf, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log(f"news file error ({nf.name}): {e}")
            continue

        if not isinstance(data, dict):
            log(f"news file format unexpected ({nf.name}), skipping")
            continue

        before = len(data)
        data = {url: ts for url, ts in data.items() if ts >= cutoff}
        purged = before - len(data)
        total_purged += purged

        if purged > 0:
            try:
                with open(nf, "w") as f:
                    json.dump(data, f, indent=2)
                log(f"{nf.name}: purged {purged} old entries ({before}→{len(data)})")
            except OSError as e:
                log(f"news file write error ({nf.name}): {e}")

    if total_purged == 0:
        log("no old news to purge")


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

    # 2. Old news
    clean_old_news()

    # 3. npm cache
    run_cmd(["npm", "cache", "clean", "--force"], "npm cache")

    # 4. pnpm store
    run_cmd(["pnpm", "store", "prune"], "pnpm store")

    # 5. pip cache
    run_cmd([sys.executable, "-m", "pip", "cache", "purge"], "pip cache")

    log("=== cleanup done ===")


if __name__ == "__main__":
    main()
