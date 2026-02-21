import time
import logging
from typing import List, Dict, Optional

from src.models.database import SessionLocal, TriggerEmbedding
from src.services.embedding_service import get_embedding_service
from src.config import settings
import asyncio
import numpy as np
from src.services.vector_index import VectorIndex


logger = logging.getLogger(__name__)


# Canonical starter trigger specs. Centralized seeding logic for starter data.
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
    {"name": "create_schedule", "action_type": "create_schedule", "utterance": "Påminn meg hver dag kl. 09:00", "threshold": 0.75},
    {"name": "create_schedule", "action_type": "create_schedule", "utterance": "Minne meg på hver dag klokken 09:00", "threshold": 0.75},
    {"name": "update_schedule", "action_type": "update_schedule", "utterance": "Endre påminnelsen min til kl. 20:00", "threshold": 0.75},
    {"name": "update_schedule", "action_type": "update_schedule", "utterance": "Endre påminnelse til 20:00", "threshold": 0.75},
    {"name": "next_lesson", "action_type": "next_lesson", "utterance": "Send meg neste leksjon", "threshold": 0.75},
    {"name": "next_lesson", "action_type": "next_lesson", "utterance": "Hva er neste leksjon?", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "Jeg er i Oslo", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "Min tidssone er Europe/Oslo", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "Jeg bor i Oslo", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "Jeg er i New York", "threshold": 0.75},
    {"name": "set_timezone", "action_type": "set_timezone", "utterance": "Min tidssone er America/Los_Angeles", "threshold": 0.75},
    {"name": "enter_rag", "action_type": "enter_rag", "utterance": "Bruk RAG for dette", "threshold": 0.75},
    {"name": "exit_rag", "action_type": "exit_rag", "utterance": "Slutt å bruke RAG", "threshold": 0.75},
]

# Add common phrasings for requesting today's/next lesson, including Norwegian
lesson_phrases = [
    "What's today's lesson?",
    "What is todays lesson",
    "What is today's lesson",
    "Show me today's lesson",
    "Which lesson is it today",
    "Which lesson is it today?",
    "Send me today's lesson",
    "Send me today's lesson please",
    "Give me today's lesson",
    "Give me the lesson for today",
    "Whats todays lesson",
    "what is todays lesson",
    "what is today's lesson",
    "what's today's lesson",
    "show me todays lesson",
    "which lesson is today",
    "which lesson is today?",
    "send me today's lesson",
    "today's lesson",
    "todays lesson",
    "Hva er dagens leksjon",
    "Hva er dagens leksjon?",
    "Vis meg dagens leksjon",
    "Hvilken leksjon er det i dag",
    "Vis meg leksjonen for i dag",
    "Send meg dagens leksjon",
]

# Phrases that explicitly request the raw/exact lesson text
raw_lesson_phrases = [
    "What's today's lesson?",
    "What is today's lesson?",
    "Which lesson is scheduled for today?",
    "Show me today's lesson.",
    "Send me today's lesson, please.",
    "Give me the lesson for today.",
    "Show me the full text of today's lesson.",
    "Can you provide the exact text of the lesson?",
    "What is the exact text of the lesson?",
    "Give me the exact words of the lesson.",
    "Show me the lesson text exactly as written.",
    "I want the full, verbatim lesson text.",
    "Send me the lesson text.",
    "Show the exact words of this lesson.",
    "What exactly is the lesson about?",
    "What are the exact words of this lesson?",
    "Display the lesson text.",
    "Please provide the exact text of the lesson.",
    "Give me the lesson content word-for-word.",
    "Show me the exact lesson (no summary).",
    # Norwegian variants
    "Hva er den eksakte teksten til leksjonen?",
    "Vis meg leksjonsteksten ordrett.",
    "Gi meg den eksakte teksten til leksjonen.",
    "Gi meg de eksakte ordene i leksjonen.",
    "Vis meg leksjonsteksten.",
    "Send meg leksjonsteksten.",
    "Gi meg leksjonens tekst ordrett.",
    "Hva er den eksakte teksten i leksjonen?",
    "Hva er leksjonsteksten?",
]
for p in raw_lesson_phrases:
    STARTER.append({"name": "raw_lesson", "action_type": "raw_lesson", "utterance": p, "threshold": 0.75})
for p in lesson_phrases:
    STARTER.append({"name": "next_lesson", "action_type": "next_lesson", "utterance": p, "threshold": 0.75})

# Greetings (used for lightweight auto-send/confirmation gating)
greeting_phrases = [
    "hi",
    "hello",
    "hey",
    "good morning",
    "good evening",
    "good afternoon",
    "hei",
    "hallo",
    "god morgen",
    "god kveld",
    "god ettermiddag",
]
for p in greeting_phrases:
    STARTER.append({"name": "greeting", "action_type": "greeting", "utterance": p, "threshold": 0.55})

# Confirmation intents for lesson completion prompts
confirm_yes_phrases = [
    "yes I completed it",
    "yes finished the lesson",
    "finished the lesson",
    "done with that lesson",
    "jeg er ferdig",
    "ja ferdig",
]
for p in confirm_yes_phrases:
    STARTER.append({"name": "confirm_yes", "action_type": "confirm_yes", "utterance": p, "threshold": 0.55})

confirm_no_phrases = [
    "not yet, still working on it",
    "no I haven't finished",
    "I need more time",
    "nei ikke ferdig",
    "jeg er ikke ferdig ennå",
]
for p in confirm_no_phrases:
    STARTER.append({"name": "confirm_no", "action_type": "confirm_no", "utterance": p, "threshold": 0.55})

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
    # Norwegian variants
    "har jeg noen påminnelser",
    "hvilke påminnelser har jeg",
    "hva påminnelser har jeg",
    "har jeg en plan",
    "har jeg en påminnelse",
    "hva er planen min",
    "vis mine påminnelser",
    "list påminnelsene mine",
    "hvilke avtaler har jeg",
]

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

for c in CURATED_CONFIRMATIONS:
    STARTER.append({"name": "update_schedule", "action_type": "update_schedule", "utterance": c, "threshold": 0.75})


async def seed_triggers() -> None:
    """Embed and persist the canonical `STARTER` triggers into the DB.

    Centralized seeding logic for starter trigger data.
    """
    # Import inside the function so tests can monkeypatch the embedding
    # service factory (`src.services.embedding_service.get_embedding_service`)
    # before this module is imported.
    from src.services.embedding_service import get_embedding_service as _get_embedding_service
    emb_svc = _get_embedding_service()
    texts = [s["utterance"] for s in STARTER]
    embeddings = await emb_svc.batch_embed(texts)

    db = SessionLocal()
    try:
        for spec, emb in zip(STARTER, embeddings):
            if emb is None:
                continue
            b = emb_svc.embedding_to_bytes(emb)
            t = TriggerEmbedding(name=spec.get("name") or spec.get("utterance"), action_type=spec["action_type"], embedding=b, threshold=spec.get("threshold", 0.75))
            db.add(t)
        db.commit()
        logger.info("Seeded trigger_embeddings from STARTER")
    finally:
        db.close()


class TriggerMatcher:
    """Loads trigger embeddings from DB and matches incoming text."""

    def __init__(self, refresh_secs: Optional[int] = None):
        self.refresh_secs = refresh_secs or settings.TRIGGER_MATCHER_REFRESH_SECS
        self._loaded_at = 0.0
        self._triggers: List[Dict] = []
        self.embedding_service = get_embedding_service()
        self._vector_index: Optional[VectorIndex] = None
        self._id_to_trigger: Dict[int, Dict] = {}

    def _load_triggers(self):
        now = time.time()
        if self._triggers and (now - self._loaded_at) < self.refresh_secs:
            return

        db = SessionLocal()
        try:
            rows = db.query(TriggerEmbedding).all()
            results = []
            for r in rows:
                results.append({
                    "trigger_id": r.id,
                    "name": r.name,
                    "action_type": r.action_type,
                    "embedding": r.embedding,
                    "threshold": float(r.threshold or settings.TRIGGER_SIMILARITY_THRESHOLD),
                })
            self._triggers = results
            self._loaded_at = now
            # Build an in-memory vector index for fast matching (optional Faiss)
            try:
                ids = []
                embs = []
                self._id_to_trigger = {}
                for t in self._triggers:
                    emb_bytes = t.get("embedding")
                    emb = None
                    if emb_bytes:
                        try:
                            emb = self.embedding_service.bytes_to_embedding(emb_bytes)
                        except Exception:
                            emb = None
                    if emb:
                        ids.append(int(t["trigger_id"]))
                        embs.append(emb)
                        self._id_to_trigger[int(t["trigger_id"])]=t
                if ids and embs:
                    vi = VectorIndex()
                    vi.build(ids, embs)
                    self._vector_index = vi
                else:
                    self._vector_index = None
            except Exception as e:
                logger.debug(f"Failed to build trigger vector index: {e}")
            logger.info(f"Loaded {len(self._triggers)} triggers for matcher")
        finally:
            db.close()

    async def _ensure_triggers_populated(self):
        """If the trigger_embeddings table is empty, populate it using the
        canonical STARTER list (defined in this module) to avoid duplicate logic.
        """
        try:
            db = SessionLocal()
            try:
                count = db.query(TriggerEmbedding).count()
                if count > 0:
                    return
            finally:
                db.close()

            # During test runs we should NOT attempt to auto-seed embeddings
            # from a live embedding service. Use settings flag to detect tests.
            if getattr(settings, "IS_TEST_ENV", False):
                logger.error("Trigger embeddings missing during test run; refusing to auto-seed. Ensure scripts/ci_trigger_data.py is present or tests seed the DB.")
                return

            await seed_triggers()
        except Exception as e:
            logger.warning(f"Could not seed trigger embeddings: {e}")

    async def match_triggers(self, user_text: str, top_k: int = 3, precomputed_embedding: Optional[List[float]] = None) -> List[Dict]:
        """Match triggers for the provided text and return top_k matches.

        Returns list of dicts: {trigger_id, name, action_type, score, threshold}
        """
        if not user_text or not user_text.strip():
            return []

        self._load_triggers()

        if not self._triggers:
            # Attempt to seed default triggers if DB is empty, then reload
            await self._ensure_triggers_populated()
            self._load_triggers()

        if not self._triggers:
            return []

        if precomputed_embedding is not None:
            embedding = precomputed_embedding
        else:
            embedding = await self.embedding_service.generate_embedding(user_text)
        if not embedding:
            return []
        # Prefer vector-index based search for speed/scale
        if self._vector_index is not None:
            try:
                results = self._vector_index.search(embedding, top_k=top_k)
                matches = []
                for trigger_id, score in results:
                    t = self._id_to_trigger.get(int(trigger_id))
                    if not t:
                        continue
                    matches.append({
                        "trigger_id": t["trigger_id"],
                        "name": t["name"],
                        "action_type": t["action_type"],
                        "score": float(score),
                        "threshold": float(t.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD)),
                    })
                return matches
            except Exception:
                # If index search fails, gracefully fall back to brute-force
                logger.debug("Vector index search failed, falling back to brute-force matching")

        # Brute-force fallback (existing behavior)
        matches: List[Dict] = []
        for t in self._triggers:
            # Convert stored bytes to embedding
            try:
                stored = self.embedding_service.bytes_to_embedding(t["embedding"]) if t.get("embedding") else None
            except Exception:
                stored = None

            if not stored:
                continue

            # Ensure embeddings have compatible sizes; pad shorter vector with zeros
            try:
                a = np.array(embedding, dtype=float)
                b = np.array(stored, dtype=float)
                if a.size != b.size:
                    maxlen = max(a.size, b.size)
                    a_p = np.zeros(maxlen, dtype=float)
                    b_p = np.zeros(maxlen, dtype=float)
                    a_p[: a.size] = a
                    b_p[: b.size] = b
                    score = self.embedding_service.cosine_similarity(a_p.tolist(), b_p.tolist())
                else:
                    score = self.embedding_service.cosine_similarity(embedding, stored)
            except Exception:
                # Fallback to zero similarity on error
                score = 0.0
            matches.append({
                "trigger_id": t["trigger_id"],
                "name": t["name"],
                "action_type": t["action_type"],
                "score": float(score),
                "threshold": float(t.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD)),
            })

        # Sort by score desc and return top_k
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:top_k]


# Module-level singleton
_matcher: Optional[TriggerMatcher] = None


def get_trigger_matcher() -> TriggerMatcher:
    global _matcher
    if _matcher is None:
        _matcher = TriggerMatcher()
    return _matcher
