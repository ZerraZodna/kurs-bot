"""Text normalization functions for ACIM lessons."""
from __future__ import annotations

import re
from typing import Optional


def _normalize_sentence_spacing(text: str) -> str:
    """Repair common PDF/OCR spacing artifacts after sentence punctuation."""
    s = text or ""
    # Add missing space after punctuation when next token starts a new word/quote.
    s = re.sub(r'([\.,!?])(?=[A-Za-z""])', r'\1 ', s)
    # Add missing space after closing quotes before a letter.
    s = re.sub(r'([''"])(?=[A-Za-z])', r'\1 ', s)
    # Collapse accidental multi-spaces introduced during repair.
    s = re.sub(r' {2,}', ' ', s)
    return s


def _normalize_lesson_content_header(content: str, lesson_id: int) -> str:
    """Ensure lesson content starts with canonical `Lesson <id>` header."""
    txt = (content or '').strip()
    if not txt:
        return txt

    # Convert leading variants like `lesson 14`, `LESSON 14`, `lesson 14 to 20`
    # into `Lesson 14` to enforce a stable canonical prefix.
    txt = re.sub(
        r'(?is)^\s*lesson\s+\d{1,3}(?:\s*(?:to|-|–)\s*\d{1,3})?\b',
        f'Lesson {lesson_id}',
        txt,
        count=1,
    )

    # If no leading lesson header exists, prepend one.
    if not re.match(rf'(?i)^\s*Lesson\s+{lesson_id}\b', txt):
        txt = f'Lesson {lesson_id}\n\n{txt}'

    # Lesson 1 formatting preference: keep this sentence attached to the prior paragraph.
    txt = re.sub(
        r'\n\n(One thing is like another as far as the application of the idea is concerned\.)',
        r' \1',
        txt,
        flags=re.I,
    )

    return txt

