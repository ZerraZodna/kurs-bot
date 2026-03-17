"""Migration helper (moved into scripts/utils).

Adjusted REPO_ROOT so the script works from the new location.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Union


def load_dotenv(repo_root: Union[str, Path]) -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ if not set.

    This avoids adding a dependency on python-dotenv while providing the
    expected behavior: environment variables in `.env` are used when present.
    """
    env_path = Path(repo_root) / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def main():
    parser = argparse.ArgumentParser(description="Run alembic migrations against dev or prod DB")
    parser.add_argument(
        "--db",
        choices=("dev", "prod"),
        help="Target database (optional). If omitted, DATABASE_URL from environment/.env is used",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm fallback stamping on failure")
    args = parser.parse_args()
    # Ensure project root is importable and load .env if present
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(REPO_ROOT)

    if args.db:
        db_map = {
            "dev": "sqlite:///./src/data/dev.db",
            "prod": "sqlite:///./src/data/prod.db",
        }
        url = db_map[args.db]
        os.environ["DATABASE_URL"] = url
    else:
        url = os.environ.get("DATABASE_URL")
        if not url:
            # fall back to dev for safety
            url = "sqlite:///./src/data/dev.db"
            os.environ["DATABASE_URL"] = url

    # Ensure project root is importable
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    try:
        from alembic import command
        from alembic.config import Config
    except Exception as e:
        print("Alembic not available in this environment:", e)
        sys.exit(1)

    cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))

    print(f"Running Alembic upgrade heads against {args.db} ({url})")
    try:
        command.upgrade(cfg, "heads")
        print("Alembic upgrade completed")
        return 0
    except Exception as e:
        print("Alembic upgrade failed with error:")
        print(e)
        print("\nAttempting safe fallback: stamping current heads to the DB so migrations are not re-applied.")
        if not args.yes:
            reply = input("Proceed with stamping (marks migrations as applied without running them)? (yes/no): ")
            if reply.lower() != "yes":
                print("Aborted. Inspect the database and migration history, then retry.")
                return 2
        try:
            command.stamp(cfg, "heads")
            print("Alembic stamp completed — DB marked as at heads (no schema changes applied).")
            print(
                "If required tables are still missing, run `python scripts/utils/fix_dev_db.py` to add missing objects."
            )
            return 0
        except Exception as e2:
            print("Stamping also failed:")
            print(e2)
            return 3


if __name__ == "__main__":
    sys.exit(main())
