"""Lesson intent detection module.

Centralizes all lesson-related detection logic that was previously scattered
across onboarding/detectors.py and lessons/handler.py.
"""

import re
from typing import Optional, Dict, Any


def detect_lesson_request(text: str) -> Optional[Dict[str, Any]]:
    """
    Detect if user is requesting information about a specific lesson.

    Examples:
    - "Tell me about lesson 10"
    - "What is lesson 5?"
    - "Explain lesson 42"
    - "Lesson 1 content"

    Returns:
        Dict with lesson_id if detected, None otherwise
    """
    # Normalize input for robust matching: lowercase, replace punctuation
    # with spaces, and collapse multiple whitespace.
    raw = text or ""
    text_lower = raw.lower()
    text_normalized = re.sub(r"[^\w\s]", " ", text_lower)
    text_normalized = re.sub(r"\s+", " ", text_normalized).strip()
    tokens = set(text_normalized.split())

    def _extract_number(s: str) -> Optional[int]:
        patterns = [
            r"\b(?:lesson|leksjon|lekse|day)\s*(?:number|nr|no|text|tekst|content|innhold)?\s*#?\s*(\d{1,3})\b",
            r"\b(?:lesson|leksjon|lekse)\s*(?:text|tekst|content|innhold)\s*#?\s*(\d{1,3})\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, s)
            if not m:
                continue
            try:
                n = int(m.group(1))
            except Exception:
                return None
            if 1 <= n <= 365:
                return n
        return None

    # 1) explicit numbered lesson
    num = _extract_number(text_normalized)
    if num:
        return {"lesson_id": num}

    # Note: "today's lesson" keyword detection removed to prevent hijacking.
    # The AI function calling system (send_todays_lesson) should handle this instead.
    # This prevents issues where complex requests like "remind me about todays lesson"
    # incorrectly return the lesson content instead of creating reminders.

    return None


def handle_lesson_status_response(text: str) -> Dict[str, Any]:
    """Handle user's response about whether they're new or continuing.

    Uses structured facts to store a `current_lesson` memory when
    an explicit lesson number is provided, and to avoid re-asking the 'new/continue'
    question when facts indicate the user is continuing or has completed the course.

    Returns the detector response dict for downstream handling.
    """
    text_orig = text
    text_lower = text.lower().strip()

    # Detect explicit lesson numbers (e.g., 'lesson 6', 'leksjon 6')
    lesson_match = re.search(r"(?:lesson|leksjon)\s*(\d{1,3})", text_lower)
    lesson_num = None
    if lesson_match:
        try:
            n = int(lesson_match.group(1))
            if 1 <= n <= 365:
                lesson_num = n
        except Exception:
            lesson_num = None

    # Detect phrases that imply the user has done/completed the course before
    completed_patterns = [
        r"\bdone the course\b",
        r"\bcompleted the course\b",
        r"\bfinished the course\b",
        r"\b(i'?ve|i have) (done|completed|finished)\b",
        r"\bdone this course\b",
        r"\b(been through|went through) the course\b",
        r"\bhave done it before\b",
        r"\bdone it before\b",
    ]
    completed_before = any(re.search(p, text_lower) for p in completed_patterns)

    # Detect new user intent
    new_patterns = [
        r"\bnew\b",
        r"\bfirst time\b",
        r"\bnever (done|seen|used)\b",
        r"\bny\b",
        r"\bnybegynner\b",
        r"\bforste gang\b",
        r"\bførste gang\b",
    ]
    is_new = any(re.search(p, text_lower) for p in new_patterns)

    # Detect continuing intent (generic) and common natural phrases
    continuing_patterns = [
        r"\bcontinuing\b",
        r"\bcontinu(ed|e)\b",
        r"\balready\b",
        r"\bstarted\b",
        r"\bbegun\b",
        r"\bbegan\b",
        r"\b(on|at) lesson\b",
        r"\bleksjon\b",
        # Contractions / common phrasings
        r"i\s*(?:have|ve)\s*(?:begun|started)",
        r"i\s*(?:have|ve)\s*(?:been )?working",
        r"i\s*(?:have|ve)\s*(?:been )?doing",
        r"i\s*started\b",
        r"i've\s*started",
    ]
    is_continuing = any(re.search(p, text_lower) for p in continuing_patterns) or completed_before

    # Build structured facts for downstream consumption
    facts = {"lesson_number": lesson_num, "is_new": bool(is_new), "is_continuing": bool(is_continuing), "completed_before": bool(completed_before)}

    # Decision logic: prefer explicit lesson numbers
    if lesson_num is not None:
        return {"action": "send_specific_lesson", "lesson_id": lesson_num, "facts": facts}

    if is_new:
        return {"action": "send_lesson_1", "facts": facts}

    if is_continuing:
        return {"action": "ask_lesson_number", "facts": facts}

    return {"action": "clarify", "facts": facts, "original": text_orig}


__all__ = [
    "detect_lesson_request",
    "handle_lesson_status_response",
]
