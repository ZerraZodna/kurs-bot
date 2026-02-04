from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class MemoryDecision:
    store: bool
    key: Optional[str]
    value: Optional[str]
    confidence: float
    ttl_hours: Optional[int]
    source: str


SENSITIVE_HINTS = (
    "health",
    "medical",
    "diagnosis",
    "lawyer",
    "legal",
    "court",
    "ssn",
    "passport",
    "credit card",
    "bank account",
)

SKIP_HINTS = (
    "just kidding",
    "lol",
    "lmao",
    "jk",
)

CORRECTION_HINTS = (
    "actually",
    "no, my",
    "i meant",
    "correction",
)

ALWAYS_STORE_HINTS = (
    "my name is",
    "i am",
    "my goal is",
    "i want to",
    "i prefer",
    "my email is",
    "my phone is",
)


def decide_memory_store(
    user_message: str,
    conversation_context: Optional[str] = None,
    user_consent_flags: Optional[Dict[str, bool]] = None,
    candidate_key: Optional[str] = None,
    candidate_value: Optional[str] = None,
    source: str = "dialogue_engine",
) -> MemoryDecision:
    """
    Rule-based memory storage decision.

    Returns a MemoryDecision with the store/skip outcome.
    """
    message = (user_message or "").strip().lower()
    consent = user_consent_flags or {}

    if not message:
        return MemoryDecision(False, None, None, 0.0, None, source)

    if any(hint in message for hint in SKIP_HINTS):
        return MemoryDecision(False, None, None, 0.1, None, source)

    if any(hint in message for hint in SENSITIVE_HINTS) and not consent.get("sensitive", False):
        return MemoryDecision(False, None, None, 0.2, None, source)

    ttl_hours: Optional[int] = None
    confidence = 0.6

    if any(hint in message for hint in CORRECTION_HINTS):
        confidence = 0.9

    if any(hint in message for hint in ALWAYS_STORE_HINTS):
        confidence = max(confidence, 0.85)

    key = candidate_key
    value = candidate_value

    if key is None and value is None:
        # Minimal heuristic: store the message as a raw user_fact
        key = "user_fact"
        value = user_message.strip()
        ttl_hours = 24 if "today" in message or "tomorrow" in message else None

    return MemoryDecision(True, key, value, confidence, ttl_hours, source)
