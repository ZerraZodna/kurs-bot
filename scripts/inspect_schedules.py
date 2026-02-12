import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scheduler import SessionLocal
from src.models.database import Schedule, User

if __name__ == '__main__':
    db = SessionLocal()
    rows = db.query(Schedule).order_by(Schedule.schedule_id.desc()).limit(50).all()
    for r in rows:
        user = db.query(User).filter_by(user_id=r.user_id).first()
        print(r.schedule_id, r.user_id, getattr(user, 'channel', None), getattr(user, 'external_id', None), r.schedule_type, r.cron_expression, r.next_send_time, r.last_sent_at, r.is_active)
    db.close()
