import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.scheduler import SessionLocal
from src.models.database import MessageLog

if __name__ == '__main__':
    db = SessionLocal()
    rows = db.query(MessageLog).order_by(MessageLog.message_id.desc()).limit(50).all()
    for r in rows:
        print(r.message_id, r.user_id, r.direction, r.status, r.error_message, r.created_at)
    db.close()
