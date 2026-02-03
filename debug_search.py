"""
Debug semantic search
"""
from src.models.database import SessionLocal, Memory
from src.services.embedding_service import get_embedding_service

session = SessionLocal()

# Check stored memories
memories = session.query(Memory).filter_by(user_id=1, is_active=True).all()
print(f"Found {len(memories)} active memories for user 1")

for m in memories:
    has_emb = "✅" if m.embedding else "❌"
    emb_len = len(m.embedding) if m.embedding else 0
    print(f"{has_emb} {m.key}: embedding={emb_len} bytes, value={m.value[:30]}...")

# Try to deserialize one
if memories and memories[0].embedding:
    embedding_service = get_embedding_service()
    recovered = embedding_service.bytes_to_embedding(memories[0].embedding)
    if recovered:
        print(f"\n✅ Successfully deserialized embedding: {len(recovered)} dimensions")
        print(f"   First 5 values: {recovered[:5]}")
    else:
        print("\n❌ Failed to deserialize embedding")

session.close()
