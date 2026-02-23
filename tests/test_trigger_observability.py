import pytest

from src.models.database import SessionLocal, TriggerEmbedding
from src.triggers.trigger_matcher import TriggerMatcher


class DummyEmbedSvc:
    def embedding_to_bytes(self, emb):
        import numpy as np

        return np.array(emb, dtype="float32").tobytes()

    def bytes_to_embedding(self, data):
        import numpy as np

        return np.frombuffer(data, dtype="float32").tolist()

    def cosine_similarity(self, a, b):
        import numpy as np

        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        if np.linalg.norm(va) == 0 or np.linalg.norm(vb) == 0:
            return 0.0
        return float((va / np.linalg.norm(va)) @ (vb / np.linalg.norm(vb)))

    async def generate_embedding(self, text: str):
        t = (text or "").lower()
        if any(k in t for k in ("remind", "ping", "nudge", "daily", "every day")):
            return [1.0, 0.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0, 0.0]


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _seed_minimal_triggers(db, svc: DummyEmbedSvc):
    db.query(TriggerEmbedding).delete()
    db.commit()
    db.add(
        TriggerEmbedding(
            name="create_schedule",
            action_type="create_schedule",
            embedding=svc.embedding_to_bytes([1.0, 0.0, 0.0, 0.0]),
            threshold=0.55,
        )
    )
    db.add(
        TriggerEmbedding(
            name="enter_rag",
            action_type="enter_rag",
            embedding=svc.embedding_to_bytes([0.0, 1.0, 0.0, 0.0]),
            threshold=0.55,
        )
    )
    db.commit()


@pytest.mark.asyncio
async def test_paraphrases_map_to_same_schedule_action(db):
    svc = DummyEmbedSvc()
    _seed_minimal_triggers(db, svc)

    matcher = TriggerMatcher()
    matcher.embedding_service = svc
    matcher._loaded_at = 0

    paraphrases = [
        "Please remind me every day",
        "Could you ping me daily?",
        "Give me a daily nudge",
    ]
    for phrase in paraphrases:
        matches = await matcher.match_triggers(phrase, top_k=1)
        assert matches
        assert matches[0]["action_type"] == "create_schedule"
        assert matches[0]["score"] >= matches[0]["threshold"]


@pytest.mark.asyncio
async def test_explain_match_has_structured_diagnostics(db):
    svc = DummyEmbedSvc()
    _seed_minimal_triggers(db, svc)

    matcher = TriggerMatcher()
    matcher.embedding_service = svc
    matcher._loaded_at = 0

    explanation = await matcher.explain_match("Could you ping me daily?", top_k=3)
    assert explanation["matched"] is True
    assert explanation["matched_action"] == "create_schedule"
    assert isinstance(explanation["score"], float)
    assert isinstance(explanation["threshold"], float)
    assert "fallback_path_used" in explanation
    assert explanation["top_matches"]


@pytest.mark.asyncio
async def test_handle_triggers_reports_fallback_path(monkeypatch):
    from src.triggers.triggering import handle_triggers

    class FakeMatcher:
        async def match_triggers(self, text, precomputed_embedding=None):
            if "not about schedules" in text.lower():
                return [
                    {
                        "trigger_id": 10,
                        "name": "create_schedule",
                        "action_type": "create_schedule",
                        "score": 0.10,
                        "threshold": 0.75,
                        "fallback_path_used": False,
                        "match_source": "vector_index",
                    }
                ]
            return [
                {
                    "trigger_id": 11,
                    "name": "update_schedule",
                    "action_type": "update_schedule",
                    "score": 0.95,
                    "threshold": 0.75,
                    "fallback_path_used": False,
                    "match_source": "vector_index",
                }
            ]

    class FakeDispatcher:
        def dispatch(self, match, context):
            return {"ok": True, "action": match.get("action_type")}

    monkeypatch.setattr("src.triggers.triggering.get_trigger_matcher", lambda: FakeMatcher())
    monkeypatch.setattr(
        "src.triggers.triggering.get_trigger_dispatcher",
        lambda session, memory_manager: FakeDispatcher(),
    )

    diagnostics = await handle_triggers(
        response="Your daily reminder at 15:00 is now set.",
        original_text="This is not about schedules",
        session=None,
        memory_manager=None,
        user_id=42,
        original_text_embedding=[0.0, 0.0, 0.0, 1.0],
    )

    assert diagnostics["original_text_decision"]["matched"] is False
    assert diagnostics["assistant_response_decision"]["matched"] is True
    assert diagnostics["assistant_response_decision"]["matched_action"] == "update_schedule"
    assert diagnostics["assistant_response_decision"]["fallback_path_used"] is True
    assert "update_schedule" in diagnostics["dispatched_actions"]


@pytest.mark.asyncio
async def test_debug_trigger_command_returns_explanation(monkeypatch):
    from src.services.dialogue.command_handlers import handle_debug_trigger_match

    class FakeMatcher:
        async def explain_match(self, user_text, top_k=5, precomputed_embedding=None):
            return {
                "matched": False,
                "matched_action": None,
                "score": 0.42,
                "threshold": 0.75,
                "fallback_path_used": False,
                "match_source": "vector_index",
                "top_matches": [
                    {"action_type": "next_lesson", "score": 0.42, "threshold": 0.75}
                ],
            }

    monkeypatch.setattr(
        "src.services.dialogue.command_handlers.get_trigger_matcher",
        lambda: FakeMatcher(),
    )

    response = await handle_debug_trigger_match("debug_trigger just chatting", user_id=9)
    assert response is not None
    assert "matched=false" in response
    assert "score=0.420" in response
    assert "threshold=0.750" in response
    assert "top_candidates:" in response
