"""Lesson intent detection module.

Centralizes lesson-related detection logic for onboarding flow.
"""

import re
from typing import Dict, Any


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
    "handle_lesson_status_response",
]

