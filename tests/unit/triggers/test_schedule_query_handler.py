"""
Migrated tests for schedule query handler.
 migrated from tests/test_schedule_query_handler.py
"""
import pytest

from src.scheduler import schedule_query_handler
import src.triggers.trigger_matcher as trigger_matcher


class DummyEmbedSvc:
    """Dummy embedding service for testing."""

    def __init__(self):
        pass

    async def batch_embed(self, texts):
        # Map status-like examples (contain 'remind' or 'reminders') to vector [1,0,0]
        # Map change-like examples (contain 'change' or 'set' or 'update' or 'remind me at') to [0,1,0]
        out = []
        for t in texts:
            tt = (t or "").lower()
            if "remind" in tt or "reminders" in tt:
                out.append([1.0, 0.0, 0.0])
            elif any(x in tt for x in ("change", "set", "update", "remind me at", "add another")):
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out

    async def generate_embedding(self, text: str):
        tt = (text or "").lower()
        if "change" in tt or "set" in tt or "update" in tt or ("remind" in tt and ":" in tt):
            return [0.0, 1.0, 0.0]
        if "remind" in tt or "reminder" in tt or "reminders" in tt:
            return [1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0]

    def cosine_similarity(self, a, b):
        # simple dot-product over normalized vectors
        import math
        def norm(v):
            s = sum(x * x for x in v)
            return math.sqrt(s) if s > 0 else 0.0

        na = norm(a)
        nb = norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return sum(x * y for x, y in zip(a, b)) / (na * nb)


@pytest.mark.asyncio
async def test_change_phrase_not_detected_as_status(monkeypatch):
    """Given: A user asks to change their reminder time
    When: Detecting if it's a schedule status request
    Then: It should NOT be detected as a status request
    """
    # Given: Patch the trigger matcher with dummy service
    svc = DummyEmbedSvc()

    class DummyMatcher:
        def __init__(self, svc):
            self.svc = svc

        async def match_triggers(self, text, top_k=3):
            msg_emb = await self.svc.generate_embedding(text)
            status_emb = [1.0, 0.0, 0.0]
            change_emb = [0.0, 1.0, 0.0]
            status_score = self.svc.cosine_similarity(msg_emb, status_emb)
            change_score = self.svc.cosine_similarity(msg_emb, change_emb)
            matches = [
                {"trigger_id": 1, "name": "query_schedule", "action_type": "query_schedule", "score": float(status_score), "threshold": 0.75},
                {"trigger_id": 2, "name": "update_schedule", "action_type": "update_schedule", "score": float(change_score), "threshold": 0.75},
            ]
            matches.sort(key=lambda x: x["score"], reverse=True)
            return matches[:top_k]

    monkeypatch.setattr(trigger_matcher, "get_trigger_matcher", lambda: DummyMatcher(svc))

    # When: User asks to change their reminder
    text = "Change lesson reminder to 09:00"
    is_status = await schedule_query_handler.detect_schedule_status_request(text)
    
    # Then: Should NOT be detected as a status request
    assert not is_status

    # When: User uses a typo variant
    typo_text = "Change lesson remder to 09:00"
    is_status_typo = await schedule_query_handler.detect_schedule_status_request(typo_text)
    
    # Then: Should NOT be detected as a status request
    assert not is_status_typo

    # Control: a status-like query should be detected
    status_text = "What reminders do I have?"
    is_status2 = await schedule_query_handler.detect_schedule_status_request(status_text)
    assert is_status2


@pytest.mark.asyncio
async def test_explicit_change_phrase_not_detected(monkeypatch):
    """Given: A user explicitly asks to change their reminder
    When: Detecting if it's a schedule status request
    Then: It should NOT be detected as a status request
    """
    # Given: Patch with another dummy matcher
    svc = DummyEmbedSvc()

    class DummyMatcher2:
        def __init__(self, svc):
            self.svc = svc

        async def match_triggers(self, text, top_k=3):
            msg_emb = await self.svc.generate_embedding(text)
            status_emb = [1.0, 0.0, 0.0]
            change_emb = [0.0, 1.0, 0.0]
            status_score = self.svc.cosine_similarity(msg_emb, status_emb)
            change_score = self.svc.cosine_similarity(msg_emb, change_emb)
            matches = [
                {"trigger_id": 1, "name": "query_schedule", "action_type": "query_schedule", "score": float(status_score), "threshold": 0.75},
                {"trigger_id": 2, "name": "update_schedule", "action_type": "update_schedule", "score": float(change_score), "threshold": 0.75},
            ]
            matches.sort(key=lambda x: x["score"], reverse=True)
            return matches[:top_k]

    monkeypatch.setattr(trigger_matcher, "get_trigger_matcher", lambda: DummyMatcher2(svc))

    # When: User asks to change their reminder
    text = "Change lesson reminder to 09:00"
    is_status = await schedule_query_handler.detect_schedule_status_request(text)
    
    # Then: Should NOT be detected as a status request
    assert not is_status

