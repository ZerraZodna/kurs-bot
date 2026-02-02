"""
Reset dev.db to a clean state while preserving ACIM lessons.

This script:
1. Backs up current lessons to memory
2. Clears all data from non-lesson tables
3. Re-imports the lessons
4. Leaves you with a clean DB ready for testing

Usage:
    python scripts/reset_dev_db.py              # Reset with confirmation
    python scripts/reset_dev_db.py --force      # Reset without confirmation
    python scripts/reset_dev_db.py --backup     # Backup DB to .bak file first
    python scripts/reset_dev_db.py --lessons-only  # Just preserve lessons
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import (
    SessionLocal, Base, engine, 
    User, Memory, Schedule, MessageLog, Lesson, Unsubscribe
)


def backup_database(db_path: str = "src/data/dev.db") -> str:
    """Create a backup of the current database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak.{timestamp}"
    
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        size_mb = os.path.getsize(backup_path) / 1024 / 1024
        print(f"✅ Database backed up to: {backup_path} ({size_mb:.2f} MB)")
        return backup_path
    
    return None


def get_lesson_count() -> int:
    """Get current lesson count."""
    session = SessionLocal()
    try:
        count = session.query(Lesson).count()
        return count
    finally:
        session.close()


def clear_all_except_lessons() -> dict:
    """
    Clear all tables except lessons.
    Returns stats about what was cleared.
    """
    session = SessionLocal()
    stats = {}
    
    try:
        # Count before clearing
        stats['users_before'] = session.query(User).count()
        stats['memories_before'] = session.query(Memory).count()
        stats['schedules_before'] = session.query(Schedule).count()
        stats['messages_before'] = session.query(MessageLog).count()
        stats['lessons_before'] = session.query(Lesson).count()
        stats['unsubscribes_before'] = session.query(Unsubscribe).count()
        
        # Clear (preserve lessons)
        print("🗑️  Clearing tables...")
        session.query(Schedule).delete()
        print("  ✓ Schedules cleared")
        session.query(MessageLog).delete()
        print("  ✓ Messages cleared")
        session.query(Memory).delete()
        print("  ✓ Memories cleared")
        session.query(Unsubscribe).delete()
        print("  ✓ Unsubscribes cleared")
        session.query(User).delete()
        print("  ✓ Users cleared")
        
        session.commit()
        
        # Verify
        stats['users_after'] = session.query(User).count()
        stats['memories_after'] = session.query(Memory).count()
        stats['schedules_after'] = session.query(Schedule).count()
        stats['messages_after'] = session.query(MessageLog).count()
        stats['lessons_after'] = session.query(Lesson).count()
        stats['unsubscribes_after'] = session.query(Unsubscribe).count()
        
        return stats
    except Exception as e:
        session.rollback()
        print(f"❌ Error clearing tables: {e}")
        raise
    finally:
        session.close()


def print_stats(stats: dict) -> None:
    """Print before/after statistics."""
    print("\n📊 Cleanup Results:")
    print("─" * 50)
    tables = ['users', 'memories', 'schedules', 'messages', 'unsubscribes', 'lessons']
    
    for table in tables:
        before = stats.get(f'{table}_before', 0)
        after = stats.get(f'{table}_after', 0)
        cleared = before - after
        
        if table == 'lessons':
            status = "🔒" if cleared == 0 else "❌"
            print(f"{status} {table:15} {before:6} → {after:6} (preserved)")
        else:
            status = "✓" if cleared == before else "⚠️"
            print(f"{status} {table:15} {before:6} → {after:6} (cleared {cleared})")


def main():
    parser = argparse.ArgumentParser(
        description="Reset dev.db to a clean state while preserving ACIM lessons"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup before resetting"
    )
    parser.add_argument(
        "--lessons-only",
        action="store_true",
        help="Only show lesson count and exit"
    )
    
    args = parser.parse_args()
    
    db_path = "src/data/dev.db"
    
    # Check database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    print("🔄 ACIM Lesson Database Reset Tool")
    print("=" * 50)
    
    # Show current state
    lesson_count = get_lesson_count()
    print(f"\n📖 Current lessons in database: {lesson_count}")
    
    if args.lessons_only:
        print("\n✅ Done")
        sys.exit(0)
    
    # Backup if requested
    if args.backup:
        backup_database(db_path)
    
    # Confirm unless --force
    if not args.force:
        print("\n⚠️  This will clear all user data (except lessons):")
        print("  - Users will be deleted")
        print("  - Message history will be deleted")
        print("  - User memories will be deleted")
        print("  - Schedules will be deleted")
        print("  - All lessons will be PRESERVED ✓")
        
        response = input("\n⏸️  Continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ Cancelled")
            sys.exit(0)
    
    # Clear all except lessons
    print("\n🚀 Resetting database...")
    stats = clear_all_except_lessons()
    
    # Print results
    print_stats(stats)
    
    print("\n✅ Database reset complete!")
    print(f"   Lessons preserved: {stats['lessons_after']}")
    print("\n💡 Tips:")
    print("   - Start fresh: python main.py")
    print("   - Test onboarding with a new user")
    print("   - Users will start from lesson 1 on next interaction")


if __name__ == "__main__":
    main()
