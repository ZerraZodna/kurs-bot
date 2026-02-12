#!/usr/bin/env python
"""
Pre-configured DB recipes: backup, fresh-start, clean-users, restore, list

Usage:
  python scripts/reset_recipes.py backup
  python scripts/reset_recipes.py fresh-start
  python scripts/reset_recipes.py clean-users
  python scripts/reset_recipes.py restore [--latest | INDEX]
  python scripts/reset_recipes.py list
"""

import sys
from pathlib import Path
import shutil
import os
from datetime import datetime
import subprocess


REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "src" / "data" / "dev.db"


def cmd_backup():
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.with_name(f"{DB_PATH.name}.backup.{timestamp}")
    shutil.copy2(DB_PATH, backup_path)
    size_mb = backup_path.stat().st_size / 1024 / 1024
    print(f"✅ Backup created: {backup_path}")
    print(f"   Size: {size_mb:.2f} MB")


def cmd_clean_users():
    # reuse reset_dev_db.py which resets users/messages but preserves lessons
    script = REPO_ROOT / "scripts" / "reset_dev_db.py"
    if not script.exists():
        print(f"❌ Missing script: {script}")
        return
    result = subprocess.run([sys.executable, str(script), "--force"], capture_output=False)
    sys.exit(result.returncode)


def cmd_fresh_start():
    # Delete DB and re-import lessons
    if DB_PATH.exists():
        print(f"Deleting database: {DB_PATH}")
        DB_PATH.unlink()
    else:
        print("No existing database found, continuing to import lessons.")

    # Call import script
    script = REPO_ROOT / "scripts" / "import_acim_lessons.py"
    if not script.exists():
        print(f"❌ Missing import script: {script}")
        return
    result = subprocess.run([sys.executable, str(script)], capture_output=False)
    sys.exit(result.returncode)


def find_backups():
    data_dir = DB_PATH.parent
    if not data_dir.exists():
        return []
    patterns = [f"{DB_PATH.name}.backup.*", f"{DB_PATH.name}.bak.*"]
    backups = []
    for p in data_dir.iterdir():
        for pat in patterns:
            if p.name.startswith(pat.rsplit('*',1)[0]):
                backups.append(p)
    backups = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)
    return backups


def cmd_restore(arg=None, latest=False):
    backups = find_backups()
    if not backups:
        print("No backups found in src/data/")
        return

    if latest:
        chosen = backups[0]
    elif arg is None:
        print("Available backups:")
        for i, b in enumerate(backups):
            mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  [{i}] {b.name}  ({mtime})")
        print("Run: python scripts/reset_recipes.py restore INDEX")
        print("Or: python scripts/reset_recipes.py restore --latest")
        return
    else:
        try:
            idx = int(arg)
            chosen = backups[idx]
        except Exception as e:
            print(f"Invalid index: {arg}")
            return

    print(f"Restoring backup {chosen} -> {DB_PATH}")
    shutil.copy2(chosen, DB_PATH)
    print("✅ Restore complete")


def cmd_list():
    print("Recipes:")
    print("  backup      - Create timestamped backup of src/data/dev.db")
    print("  fresh-start - Delete DB and re-import lessons")
    print("  clean-users - Clear users/messages (preserve lessons)")
    print("  restore     - Restore from backup (interactive or --latest)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd in ("backup",):
        cmd_backup()
    elif cmd in ("clean-users", "clean_users"):
        cmd_clean_users()
    elif cmd in ("fresh-start", "fresh_start"):
        cmd_fresh_start()
    elif cmd == "restore":
        if len(sys.argv) > 2 and sys.argv[2] == "--latest":
            cmd_restore(latest=True)
        elif len(sys.argv) > 2:
            cmd_restore(arg=sys.argv[2])
        else:
            cmd_restore()
    elif cmd in ("list", "help", "--help", "-h"):
        cmd_list()
    else:
        print(f"Unknown recipe: {cmd}")
        cmd_list()
        sys.exit(1)


if __name__ == "__main__":
    main()
