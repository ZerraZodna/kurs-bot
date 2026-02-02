"""
Database management utility for development.

Provides quick commands for common DB operations while preserving lessons.

Usage:
    python scripts/db_manage.py reset      # Reset DB (clears users/messages/etc but keeps lessons)
    python scripts/db_manage.py status     # Show DB status
    python scripts/db_manage.py backup     # Create backup
    python scripts/db_manage.py clean-all  # DANGER: Delete everything including lessons
    python scripts/db_manage.py info       # Show detailed DB info
"""

import sys
from pathlib import Path
import os
import shutil
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, Memory, Lesson, Schedule, MessageLog, Unsubscribe


def cmd_status():
    """Show database status."""
    session = SessionLocal()
    try:
        print("\n📊 Database Status")
        print("=" * 50)
        
        users = session.query(User).count()
        memories = session.query(Memory).count()
        lessons = session.query(Lesson).count()
        schedules = session.query(Schedule).count()
        messages = session.query(MessageLog).count()
        unsubscribes = session.query(Unsubscribe).count()
        
        print(f"👥 Users:          {users:6}")
        print(f"🧠 Memories:       {memories:6}")
        print(f"📖 Lessons:        {lessons:6}")
        print(f"📅 Schedules:      {schedules:6}")
        print(f"💬 Messages:       {messages:6}")
        print(f"🚫 Unsubscribes:   {unsubscribes:6}")
        print("=" * 50)
        
    finally:
        session.close()


def cmd_info():
    """Show detailed database info."""
    cmd_status()
    
    session = SessionLocal()
    try:
        print("\n📝 Sample Data:")
        
        # Sample user
        user = session.query(User).first()
        if user:
            print(f"\n  First user: {user.first_name} (ID: {user.user_id})")
            mems = session.query(Memory).filter(Memory.user_id == user.user_id).count()
            print(f"  - Memories: {mems}")
        else:
            print("\n  No users yet")
        
        # Sample lessons
        lessons = session.query(Lesson).filter(Lesson.lesson_id.in_([1, 182, 365])).all()
        if lessons:
            print(f"\n  Sample lessons:")
            for l in lessons:
                print(f"    - Day {l.lesson_id}: {l.title[:50]}...")
        
    finally:
        session.close()


def cmd_reset():
    """Reset database (calls reset script)."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/reset_dev_db.py", "--force"],
        capture_output=False
    )
    sys.exit(result.returncode)


def cmd_backup():
    """Create backup of dev.db."""
    db_path = "src/data/dev.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup.{timestamp}"
    
    shutil.copy2(db_path, backup_path)
    size_mb = os.path.getsize(backup_path) / 1024 / 1024
    print(f"✅ Backup created: {backup_path}")
    print(f"   Size: {size_mb:.2f} MB")


def cmd_clean_all():
    """DANGER: Delete everything including lessons."""
    print("🚨 WARNING: This will DELETE everything!")
    response = input("Type 'YES' to confirm: ").strip()
    
    if response != "YES":
        print("❌ Cancelled")
        return
    
    db_path = "src/data/dev.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✅ Database deleted: {db_path}")
        print("   Start fresh: python main.py")
    else:
        print(f"❌ Database not found: {db_path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    commands = {
        'status': cmd_status,
        'info': cmd_info,
        'reset': cmd_reset,
        'backup': cmd_backup,
        'clean-all': cmd_clean_all,
    }
    
    if cmd in commands:
        commands[cmd]()
    else:
        print(f"❌ Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
