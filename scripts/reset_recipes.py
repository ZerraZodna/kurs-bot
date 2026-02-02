"""
Quick database reset recipes.

Provides one-liners for common scenarios.

Examples:
    # Clean slate - delete everything, then re-import lessons
    python scripts/reset_recipes.py fresh-start
    
    # Just clear user data (keep lessons)
    python scripts/reset_recipes.py clean-users
    
    # Backup current DB
    python scripts/reset_recipes.py backup
    
    # Show all available recipes
    python scripts/reset_recipes.py list
"""

import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def recipe_fresh_start():
    """Complete fresh start: Delete DB and re-import lessons."""
    print("🔄 Fresh Start Recipe")
    print("=" * 50)
    print("This will:")
    print("  1. Delete dev.db completely")
    print("  2. Re-import all 365 ACIM lessons")
    print("  3. Give you a completely clean DB with lessons")
    
    response = input("\n⏸️  Continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Cancelled")
        return
    
    # Delete DB
    db_path = "src/data/dev.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("\n✓ Deleted dev.db")
    
    # Re-import lessons
    print("✓ Re-importing lessons...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/import_acim_lessons.py", "--clear"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Lessons imported successfully")
        print("\n✅ Fresh start complete!")
        print("   Your DB now has 365 ACIM lessons and zero users")
    else:
        print(f"❌ Import failed: {result.stderr}")


def recipe_clean_users():
    """Clean user data but keep lessons."""
    print("🧹 Clean Users Recipe")
    print("=" * 50)
    print("This will clear:")
    print("  - All users")
    print("  - All memories")
    print("  - All messages")
    print("  - All schedules")
    print("  + Keep all 365 lessons ✓")
    
    response = input("\n⏸️  Continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Cancelled")
        return
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/reset_dev_db.py", "--force"],
        capture_output=False
    )
    
    if result.returncode == 0:
        print("\n✅ Clean users complete!")


def recipe_backup():
    """Create timestamped backup of DB."""
    print("💾 Backup Recipe")
    print("=" * 50)
    
    db_path = "src/data/dev.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup.{timestamp}"
    
    shutil.copy2(db_path, backup_path)
    size_mb = os.path.getsize(backup_path) / 1024 / 1024
    
    print(f"✅ Backup created!")
    print(f"   File: {backup_path}")
    print(f"   Size: {size_mb:.2f} MB")


def recipe_restore_from_backup():
    """Restore from latest backup."""
    print("📦 Restore from Backup Recipe")
    print("=" * 50)
    
    db_path = "src/data/dev.db"
    data_dir = "src/data"
    
    # Find latest backup
    backups = sorted([
        f for f in os.listdir(data_dir) 
        if f.startswith("dev.db.backup.")
    ], reverse=True)
    
    if not backups:
        print("❌ No backups found")
        return
    
    print(f"Available backups:")
    for i, backup in enumerate(backups[:5], 1):
        path = os.path.join(data_dir, backup)
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"  {i}. {backup} ({size_mb:.2f} MB)")
    
    choice = input("\nRestore from backup #1? (yes/no): ").strip().lower()
    if choice not in ['yes', 'y']:
        print("❌ Cancelled")
        return
    
    latest_backup = os.path.join(data_dir, backups[0])
    
    # Backup current DB first
    if os.path.exists(db_path):
        current_backup = f"{db_path}.backup.before-restore.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, current_backup)
        print(f"✓ Current DB backed up to: {current_backup}")
    
    # Restore
    shutil.copy2(latest_backup, db_path)
    print(f"✅ Restored from: {backups[0]}")
    print("   Your DB is back to that state")


def recipe_list():
    """List all available recipes."""
    print("\n📋 Available Database Recipes")
    print("=" * 50)
    print("""
1. fresh-start      - Complete fresh start (delete DB, re-import lessons)
2. clean-users      - Clear all users/messages/schedules (keep lessons)
3. backup           - Create timestamped backup
4. restore          - Restore from latest backup
5. list             - Show this help

Usage:
    python scripts/reset_recipes.py <recipe-name>

Examples:
    python scripts/reset_recipes.py fresh-start
    python scripts/reset_recipes.py clean-users
    python scripts/reset_recipes.py backup
""")


def main():
    if len(sys.argv) < 2:
        recipe_list()
        return
    
    recipe = sys.argv[1].lower()
    
    recipes = {
        'fresh-start': recipe_fresh_start,
        'clean-users': recipe_clean_users,
        'backup': recipe_backup,
        'restore': recipe_restore_from_backup,
        'list': recipe_list,
        'help': recipe_list,
    }
    
    if recipe in recipes:
        recipes[recipe]()
    else:
        print(f"❌ Unknown recipe: {recipe}")
        recipe_list()


if __name__ == "__main__":
    main()
