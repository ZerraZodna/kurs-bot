#!/usr/bin/env python
"""Debug script to test trigger matching for 'List reminders'"""

import asyncio
import sys
import os

# Ensure test env is set
os.environ.setdefault("IS_TEST_ENV", "1")

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.triggers.trigger_matcher import get_trigger_matcher, refresh_trigger_matcher_cache
from src.models.database import SessionLocal, TriggerEmbedding


async def main():
    # Check what's in the DB
    db = SessionLocal()
    try:
        count = db.query(TriggerEmbedding).count()
        print(f"Total trigger embeddings in DB: {count}")
        
        # Count by action_type
        from sqlalchemy import func
        counts = db.query(
            TriggerEmbedding.action_type, 
            func.count(TriggerEmbedding.id)
        ).group_by(TriggerEmbedding.action_type).all()
        print("\nAction type counts:")
        for at, c in counts:
            print(f"  {at}: {c}")
        
        # Look for query_schedule triggers
        query_schedules = db.query(TriggerEmbedding).filter(
            TriggerEmbedding.action_type == "query_schedule"
        ).all()
        print(f"\nquery_schedule triggers: {len(query_schedules)}")
        for qs in query_schedules[:5]:
            print(f"  - {qs.name}")
    finally:
        db.close()
    
    # Refresh the matcher cache
    refresh_trigger_matcher_cache()
    
    # Test matching
    matcher = get_trigger_matcher()
    text = "List reminders"
    
    print(f"\n--- Testing match for: '{text}' ---")
    matches = await matcher.match_triggers(text, top_k=5)
    
    print(f"\nTop matches:")
    for m in matches:
        print(f"  action_type: {m['action_type']}, score: {m['score']:.4f}, threshold: {m['threshold']}")
    
    # Check detect_schedule_status_request logic
    max_status = max((m["score"] for m in matches if m.get("action_type") == "query_schedule"), default=0.0)
    max_change = max((m["score"] for m in matches if m.get("action_type") in ("update_schedule", "create_schedule")), default=0.0)
    
    print(f"\nmax_status (query_schedule): {max_status:.4f}")
    print(f"max_change (create/update): {max_change:.4f}")
    print(f"Would detect_schedule_status_request return True? {max_status >= 0.75 and max_status >= max_change}")


if __name__ == "__main__":
    asyncio.run(main())

