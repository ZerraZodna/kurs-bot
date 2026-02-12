import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scheduler import SessionLocal
from src.models.database import User

if __name__ == '__main__':
    db = SessionLocal()
    for u in db.query(User).all():
        print(u.user_id, u.external_id, u.channel, u.first_name, getattr(u,'timezone', None))
    db.close()
