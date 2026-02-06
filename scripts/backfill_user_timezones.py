import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.scheduler import SessionLocal
from src.services.memory_manager import MemoryManager
from src.models.database import User


def backfill():
    db = SessionLocal()
    mm = MemoryManager(db)
    users = db.query(User).all()
    updated = 0
    for u in users:
        if getattr(u, 'timezone', None):
            continue
        mems = mm.get_memory(u.user_id, 'user_timezone')
        if mems:
            tz = mems[0].get('value')
            if tz:
                try:
                    u.timezone = tz
                    db.add(u)
                    db.commit()
                    updated += 1
                except Exception as e:
                    db.rollback()
                    print('Failed to update user', u.user_id, e)
    db.close()
    print('Backfilled', updated, 'users')

if __name__ == '__main__':
    backfill()
