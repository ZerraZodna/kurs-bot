"""Seed starter triggers into DB.

Run: python scripts/seed_triggers.py
"""
import asyncio
from src.models.database import SessionLocal, TriggerEmbedding
from src.services.embedding_service import get_embedding_service


STARTER = [
    {"name": "create_schedule", "action_type": "create_schedule", "utterance": "Please remind me every day at 9am" , "threshold": 0.75},
    {"name": "update_schedule", "action_type": "update_schedule", "utterance": "Change my reminder to 8pm", "threshold": 0.75},
    {"name": "next_lesson", "action_type": "next_lesson", "utterance": "Send me the next lesson", "threshold": 0.75},
    {"name": "enter_rag", "action_type": "enter_rag", "utterance": "Use RAG for this", "threshold": 0.75},
    {"name": "exit_rag", "action_type": "exit_rag", "utterance": "Stop using RAG", "threshold": 0.75},
]


async def main():
    svc = get_embedding_service()
    texts = [s["utterance"] for s in STARTER]
    embeds = await svc.batch_embed(texts)

    db = SessionLocal()
    try:
        for spec, emb in zip(STARTER, embeds):
            if emb is None:
                continue
            b = svc.embedding_to_bytes(emb)
            t = TriggerEmbedding(name=spec["name"], action_type=spec["action_type"], embedding=b, threshold=spec.get("threshold", 0.75))
            db.add(t)
        db.commit()
        print("Seeded triggers")
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
