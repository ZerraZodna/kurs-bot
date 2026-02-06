from pathlib import Path,sys
sys.path.insert(0,str(Path('.').resolve()))
from src.models.database import SessionLocal, TriggerEmbedding

db=SessionLocal()
rows = db.query(TriggerEmbedding).all()
print('count =', len(rows))
for r in rows:
    print(r.id, r.name, r.action_type, r.threshold)
db.close()
