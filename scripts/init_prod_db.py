"""
Initialize a clean production database.
Run this script when you want to start fresh with production data.

Usage:
    python scripts/init_prod_db.py
"""
import os
import sys
from pathlib import Path

# Ensure we're using the production database
prod_db_path = Path("src/data/prod.db")

if prod_db_path.exists():
    confirm = input(f"⚠️  {prod_db_path} already exists. Delete and recreate? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Aborted. No changes made.")
        sys.exit(0)
    
    # Backup existing database
    backup_path = prod_db_path.with_suffix('.db.backup')
    prod_db_path.rename(backup_path)
    print(f"📦 Backed up existing database to {backup_path}")

# Set environment to use prod database
os.environ['DATABASE_URL'] = 'sqlite:///./src/data/prod.db'

# Import after setting environment
import sys
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.models.database import Base, engine

print("🗄️  Creating production database schema...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print(f"✅ Production database initialized at {prod_db_path}")
print("\n📝 Next steps:")
print("1. Make sure your .env has: DATABASE_URL=sqlite:///./src/data/prod.db")
print("2. Restart your uvicorn server")
print("3. Send a message via Telegram to create your first user")

# Seed trigger embeddings into the new production DB
try:
    print("\n✨ Seeding default trigger embeddings...")
    import asyncio
    from scripts.seed_triggers import main as _seed_main
    asyncio.run(_seed_main())
    print("✅ Trigger embeddings seeded")
except Exception as e:
    print(f"⚠️  Failed to seed trigger embeddings: {e}")

# Seed prompt templates (default library)
try:
    print("\n✨ Seeding default prompt templates...")
    from scripts.seed_prompt_templates import seed as _seed_prompts
    _seed_prompts()
    print("✅ Prompt templates seeded")
except Exception as e:
    print(f"⚠️  Failed to seed prompt templates: {e}")
