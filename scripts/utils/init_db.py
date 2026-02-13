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
from pathlib import Path


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


def resolve_database_url(db_arg: str | None) -> str:
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


def init_db(database_url: str, yes: bool = False, lessons: str | None = None) -> None:
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

    # If an existing sqlite DB is present, verify embeddings dimension to avoid
    # accidental mismatches (e.g. switching embedding model dims).
    expected_dim = None
    try:
        expected_dim = int(os.environ.get('EMBEDDING_DIMENSION') or 0)
    except Exception:
        expected_dim = 0

    def _scan_db_for_mismatched_dims(path: Path, expected: int):
        if expected <= 0:
            return []
        import sqlite3
        import numpy as _np

        mismatches = []
        conn = sqlite3.connect(str(path))
        c = conn.cursor()
        c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view')")
        for name, _typ in c.fetchall():
            try:
                cols_info = c.execute(f"PRAGMA table_info({name})").fetchall()
            except Exception:
                continue
            blob_cols = [r[1] for r in cols_info if r[2] and r[2].upper().startswith('BLOB') or ('embed' in (r[1] or '').lower())]
            for col in blob_cols:
                try:
                    row = c.execute(f"SELECT {col} FROM {name} WHERE {col} IS NOT NULL LIMIT 1").fetchone()
                except Exception:
                    row = None
                if row and row[0]:
                    try:
                        arr = _np.frombuffer(row[0], dtype=_np.float32)
                        if arr.shape[0] != expected:
                            mismatches.append((name, col, int(arr.shape[0])))
                    except Exception:
                        # non-numeric blob or unexpected format
                        mismatches.append((name, col, None))
        conn.close()
        return mismatches

    if db_path_info and db_path_info.exists():
        # load .env if present to pick up EMBEDDING_DIMENSION when not in env
        repo_root = Path(__file__).resolve().parents[2]
        dotenv = repo_root / '.env'
        data = load_dotenv(dotenv)
        if not expected_dim and 'EMBEDDING_DIMENSION' in data:
            try:
                expected_dim = int(data['EMBEDDING_DIMENSION'])
            except Exception:
                expected_dim = expected_dim or 0

        # allow caller to override check via environment flag
        allow_mismatch = os.environ.get('ALLOW_EMBEDDING_DIM_MISMATCH', '').lower() in ('1','true','yes')
        # If a user passed CLI flags, they will be handled by main() wrapper which
        # may set ALLOW_EMBEDDING_DIM_MISMATCH in env before calling init_db.
        if expected_dim and not allow_mismatch:
            mism = _scan_db_for_mismatched_dims(db_path_info, expected_dim)
            if mism:
                msg_lines = [f"Found {len(mism)} embedding dimension mismatch(es):"]
                for t, c, l in mism:
                    msg_lines.append(f" - table {t}, column {c}: stored_dim={l} expected={expected_dim}")
                msg_lines.append('')
                msg_lines.append('To proceed and overwrite the DB anyway, re-run with the environment variable ALLOW_EMBEDDING_DIM_MISMATCH=1 or pass --allow-dim-mismatch to the CLI.')
                raise SystemExit('\n'.join(msg_lines))

        if not yes:
            raise SystemExit(0)
        backup_path = db_path_info.with_suffix('.db.backup')
        db_path_info.rename(backup_path)
        print(f'📦 Backed up existing database to {backup_path}')

    print('🗄️  Creating database schema...')
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    print(f'✅ Database initialized ({database_url})')
    print('\n📝 Next steps:')
    print('1. Restart your uvicorn server')
    print('2. Send a message via Telegram to create your first user')

    # Seed trigger embeddings
    try:
        print('\n✨ Seeding default trigger embeddings...')
        from scripts.utils.seed_triggers import seed as _seed_triggers
        _seed_triggers()
        print('✅ Trigger embeddings seeded')
    except Exception as e:
        print(f'⚠️  Failed to seed trigger embeddings: {e}')

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
                utils_script = repo_root / 'scripts' / 'utils' / 'import_acim_lessons.py'
                if utils_script.exists():
                    subprocess.run([sys.executable, str(utils_script), '--pdf', str(pdf_path)])
                else:
                    print('⚠️  No import_acim_lessons script found under scripts/utils/. See docs/ACIM_LESSONS_IMPORT.md')
    except Exception as e:
        print(f'⚠️  Failed during ACIM lessons import step: {e}')


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description='Initialize database and seed defaults')
    parser.add_argument('--db', help='Database to initialize. Accepts prod/dev, relative path, or full DATABASE_URL')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm recreate without prompt')
    parser.add_argument('--lessons', help='Path to ACIM lessons PDF to import (optional)')
    parser.add_argument('--build-index', action='store_true', help='If set and EMBEDDING_BACKEND=local, build hnswlib index from lessons')
    ns = parser.parse_args(argv)
    database_url = resolve_database_url(ns.db)
    init_db(database_url, yes=ns.yes, lessons=ns.lessons)
    # optionally build a local hnswlib index
    if ns.build_index:
        # determine backend and index path from env or .env
        env = os.environ.copy()
        repo_root = Path(__file__).resolve().parents[2]
        dotenv = repo_root / '.env'
        data = load_dotenv(dotenv)
        for k, v in data.items():
            if k not in env:
                env[k] = v
        backend = env.get('EMBEDDING_BACKEND', 'local')
        index_path = env.get('HNSWLIB_INDEX_PATH', 'src/data/emb_index.bin')
        if backend != 'local':
            print('⚠️  EMBEDDING_BACKEND is not set to "local" — skipping index build.')
        else:
            builder = repo_root / 'scripts' / 'utils' / 'embeddings_local.py'
            if not builder.exists():
                print('⚠️  embeddings_local.py not found under scripts/utils/ — cannot build index')
            else:
                print(f'🔨 Building local hnswlib index at {index_path} (this may take a while)')
                subprocess.run([sys.executable, str(builder), '--out', str(index_path)], env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
