"""Migration helper (moved into scripts/utils).

Adjusted REPO_ROOT so the script works from the new location.
"""
import os
import sys
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Run alembic migrations against dev or prod DB')
    parser.add_argument('--db', choices=('dev','prod'), default='dev', help='Target database')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm fallback stamping on failure')
    args = parser.parse_args()

    db_map = {
        'dev': 'sqlite:///./src/data/dev.db',
        'prod': 'sqlite:///./src/data/prod.db',
    }
    url = db_map[args.db]
    os.environ['DATABASE_URL'] = url

    # Ensure project root is importable
    REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    try:
        from alembic.config import Config
        from alembic import command
    except Exception as e:
        print('Alembic not available in this environment:', e)
        sys.exit(1)

    cfg = Config(os.path.join(REPO_ROOT, 'alembic.ini'))

    print(f"Running Alembic upgrade heads against {args.db} ({url})")
    try:
        command.upgrade(cfg, 'heads')
        print('Alembic upgrade completed')
        return 0
    except Exception as e:
        print('Alembic upgrade failed with error:')
        print(e)
        print('\nAttempting safe fallback: stamping current heads to the DB so migrations are not re-applied.')
        if not args.yes:
            reply = input('Proceed with stamping (marks migrations as applied without running them)? (yes/no): ')
            if reply.lower() != 'yes':
                print('Aborted. Inspect the database and migration history, then retry.')
                return 2
        try:
            command.stamp(cfg, 'heads')
            print('Alembic stamp completed — DB marked as at heads (no schema changes applied).')
            print('If required tables are still missing, run `python scripts/utils/fix_dev_db.py` to add missing objects.')
            return 0
        except Exception as e2:
            print('Stamping also failed:')
            print(e2)
            return 3

if __name__ == '__main__':
    sys.exit(main())
