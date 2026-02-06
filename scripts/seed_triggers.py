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
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "I'm in Oslo", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "My timezone is Europe/Oslo", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "I live in Oslo", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "I'm in New York", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "My timezone is America/Los_Angeles", "threshold": 0.75},
    {"name": "enter_rag", "action_type": "enter_rag", "utterance": "Use RAG for this", "threshold": 0.75},
    {"name": "exit_rag", "action_type": "exit_rag", "utterance": "Stop using RAG", "threshold": 0.75},
]

# Examples for users asking about their current reminders/schedules
SCHEDULE_STATUS_EXAMPLES = [
    "do i have any reminders",
    "which reminders do i have",
    "what reminders do i have",
    "do i have a schedule",
    "what is my schedule",
    "show my reminders",
    "list my reminders",
    "which schedules do i have",
]

# Add schedule-status examples as a query_schedule trigger
for ex in SCHEDULE_STATUS_EXAMPLES:
    STARTER.append({"name": "query_schedule", "action_type": "query_schedule", "utterance": ex, "threshold": 0.75})


# Add a small curated set of assistant-confirmation utterances for update_schedule
CURATED_CONFIRMATIONS = [
    "Your daily reminder at 14:50 is now set",
    "Your daily reminder at 15:00 is now set",
    "I have set your daily reminder to 15:00",
    "Got it — your daily reminder is set to 15:00",
    "Done — I set your daily reminder for 15:00",
    "Reminder updated: 15:00",
]

# Append curated confirmations to STARTER with the same threshold as other update_schedule entries
for c in CURATED_CONFIRMATIONS:
    STARTER.append({"name": "update_schedule", "action_type": "update_schedule", "utterance": c, "threshold": 0.75})


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
