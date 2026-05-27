"""Add practice_instructions column to lessons table.

Usage:
    node ./scripts/venv.js exec python scripts/migrate_practice_instructions.py --db prod

This is idempotent — safe to run multiple times.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add practice_instructions column to lessons table")
    parser.add_argument("--db", default="prod", help="Database name (prod, dev, or path)")
    ns = parser.parse_args(argv)

    # Resolve DB path
    if ns.db in ("prod", "prod.db"):
        db_path = "src/data/prod.db"
    elif ns.db in ("dev", "dev.db"):
        db_path = "src/data/dev.db"
    else:
        db_path = ns.db

    # Ensure repo root is importable
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(lessons)")
    columns = [row[1] for row in cursor.fetchall()]

    if "practice_instructions" in columns:
        print("✅ Column 'practice_instructions' already exists — nothing to do.")
        conn.close()
        return 0

    cursor.execute("ALTER TABLE lessons ADD COLUMN practice_instructions TEXT")
    conn.commit()
    print("✅ Added 'practice_instructions' column to lessons table.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
