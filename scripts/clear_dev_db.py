"""
Clear dev.db - Reset the development database

WARNING: This will delete all data in dev.db!
Make sure uvicorn is stopped before running this.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import Base, engine, SessionLocal
from sqlalchemy import text


def clear_database():
    """Drop all tables and recreate them."""
    
    db_path = Path("src/data/dev.db")
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print("=" * 80)
    print("CLEARING DEV DATABASE")
    print("=" * 80)
    print(f"Database: {db_path.absolute()}")
    print("\n⚠️  WARNING: This will delete ALL data!")
    
    # Confirm
    response = input("\nType 'YES' to confirm: ")
    if response.strip().upper() != "YES":
        print("❌ Aborted.")
        return
    
    print("\n🔄 Dropping all tables...")
    
    try:
        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        print("✓ All tables dropped")
        
        # Recreate all tables
        print("\n🔄 Recreating tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ All tables recreated")
        
        # Verify
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            print(f"\n✅ Database reset complete!")
            print(f"Tables created: {', '.join(tables)}")
        finally:
            db.close()
        
        print("\n✨ dev.db is now empty and ready for testing!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure uvicorn is stopped before running this script.")


if __name__ == "__main__":
    clear_database()
