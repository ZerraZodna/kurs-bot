import sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.scheduler import SessionLocal
from src.models.database import MessageLog

if __name__ == '__main__':
    db = SessionLocal()
    
    # Total count
    total_messages = db.query(MessageLog).count()
    print(f"Total messages in DB: {total_messages}")
    
    # Today's messages
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_rows = db.query(MessageLog).filter(MessageLog.created_at >= today_start).order_by(MessageLog.created_at.desc()).all()
    print(f"\nMessages from today ({today_start.date()}): {len(today_rows)} found")
    
    for r in today_rows:
        print(f"{r.message_id} {r.user_id} {r.direction} {r.status} {getattr(r, 'error_message', 'None')} {r.created_at}")
        print(f"CONTENT ({len(r.content or '')} chars): {r.content}")
        print("---")
    
    db.close()
