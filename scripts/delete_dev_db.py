"""
Delete dev.db completely - for a fresh start

This simply deletes the database file.
Next time you run the app, it will be recreated automatically.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def delete_dev_db():
    """Delete the dev.db file completely."""
    
    db_path = Path("src/data/dev.db")
    
    print("=" * 80)
    print("DELETE DEV DATABASE FILE")
    print("=" * 80)
    print(f"Database: {db_path.absolute()}")
    
    if not db_path.exists():
        print("✓ Database file doesn't exist (already clean)")
        return
    
    # Get file size
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f"Size: {size_mb:.2f} MB")
    
    print("\n⚠️  WARNING: This will DELETE the database file!")
    print("The file will be recreated automatically on next run.")
    
    # Confirm
    response = input("\nType 'DELETE' to confirm: ")
    if response.strip().upper() != "DELETE":
        print("❌ Aborted.")
        return
    
    try:
        db_path.unlink()
        print("\n✅ dev.db deleted successfully!")
        print("✨ Next time you start the app, a fresh database will be created.")
        
    except PermissionError:
        print("\n❌ Error: Database file is locked!")
        print("Please stop uvicorn first:")
        print("  1. Go to the uvicorn terminal")
        print("  2. Press Ctrl+C to stop the server")
        print("  3. Run this script again")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    delete_dev_db()
