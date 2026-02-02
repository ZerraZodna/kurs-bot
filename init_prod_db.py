"""
Initialize a clean production database.
Run this script when you want to start fresh with production data.
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
from src.models.database import init_db, Base, engine

print("🗄️  Creating production database schema...")
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print(f"✅ Production database initialized at {prod_db_path}")
print("\n📝 Next steps:")
print("1. Make sure your .env has: DATABASE_URL=sqlite:///./src/data/prod.db")
print("2. Restart your uvicorn server")
print("3. Send a message via Telegram to create your first user")
