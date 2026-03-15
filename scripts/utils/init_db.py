"""Initialize a database and seed defaults.

Usage:
    python scripts/utils/init_db.py --yes --db sqlite:///./src/data/prod.db --lessons path/to.pdf

If `--db` is not provided, the script will try to read `DATABASE_URL` from
the repository `.env` file or the environment.
"""
from __future__ import annotations
import os
import sys
import argparse
import subprocess
import asyncio
from pathlib import Path
from typing import List, Optional


def load_dotenv(dotenv_path: Path) -> dict:
    if not dotenv_path.exists():
        return {}
    out = {}
    for line in dotenv_path.read_text(encoding='utf8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def resolve_database_url(db_arg: Optional[str]) -> str:
    """Return a DATABASE_URL string.

    Accepts:
      - None: reads from environment or .env
      - 'prod'/'dev': maps to src/data/prod.db or dev.db
      - relative path: 'src/data/prod.db' -> sqlite:///./src/data/prod.db
      - full URL: returned as-is
    """
    if db_arg:
        val = db_arg.strip()
        if val in ('prod', 'prod.db'):
            return 'sqlite:///./src/data/prod.db'
        if val in ('dev', 'dev.db'):
            return 'sqlite:///./src/data/dev.db'
        if '://' in val:
            return val
        # treat as relative path
        p = Path(val)
        # normalize to sqlite URL
        return f'sqlite:///{p.as_posix()}'

    # fallback: check env then .env
    env_val = os.environ.get('DATABASE_URL')
    if env_val:
        return env_val
    # look for .env at repo root
    repo_root = Path(__file__).resolve().parents[2]
    dotenv = repo_root / '.env'
    data = load_dotenv(dotenv)
    if 'DATABASE_URL' in data and data['DATABASE_URL']:
        return data['DATABASE_URL']
    raise SystemExit('No DATABASE_URL provided via --db, environment, or .env')


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

def init_db(database_url: str, yes: bool = False, lessons: Optional[str] = None) -> None:
    """Initialize the specified database and seed defaults."""
    # Export DATABASE_URL for downstream imports
    os.environ['DATABASE_URL'] = database_url

    # Ensure repo root is importable
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from src.models.database import Base, engine

    db_path_info = None
    if database_url.startswith('sqlite'):
        # Try to extract file path
        if database_url.startswith('sqlite:///'):
            db_path_info = Path(database_url.replace('sqlite:///', ''))

    print('🗄️  Creating database schema...')
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    print(f'✅ Database initialized ({database_url})')
    print('\n📝 Next steps:')
    print('1. Restart your uvicorn server')
    print('2. Send a message via Telegram to create your first user')

    # Seed prompt templates
    try:
        print('\n✨ Seeding default prompt templates...')
        from scripts.utils.seed_prompt_templates import seed as _seed_prompts
        _seed_prompts()
        print('✅ Prompt templates seeded')
    except Exception as e:
        print(f'⚠️  Failed to seed prompt templates: {e}')

    # Optional: import ACIM lessons if provided
    try:
        default_pdf = Path('src/data/Sparkly ACIM lessons-extracted.pdf')
        pdf_path = Path(lessons) if lessons else (default_pdf if default_pdf.exists() else None)
        if pdf_path:
            if not pdf_path.exists():
                print(f'⚠️  Lessons PDF not found: {pdf_path} — skipping import.')
            else:
                print(f'\n==> Importing ACIM lessons from {pdf_path}')
                from src.lessons import main as import_main
                import_main(['--pdf', str(pdf_path)])

    except Exception as e:
        print(f'⚠️  Failed during ACIM lessons import step: {e}')


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Initialize database and seed defaults')
    parser.add_argument('--db', help='Database to initialize. Accepts prod/dev, relative path, or full DATABASE_URL')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm recreate without prompt')
    parser.add_argument('--lessons', help='Path to ACIM lessons PDF to import (optional)')
    ns = parser.parse_args(argv)
    database_url = resolve_database_url(ns.db)
    init_db(database_url, yes=ns.yes, lessons=ns.lessons)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
