"""Reminder and confirmation handling logic."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from src.core.timezone import to_utc
from sqlalchemy.orm import Session
from src.models.database import Lesson
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.lessons.state import (
    get_current_lesson,
    set_current_lesson,
)

logger = logging.getLogger(__name__)


async def _semantic_yes_no(text: str, onboarding_service) -> tuple[bool, bool]:
    """Classify yes/no using simple keyword matching."""
    import re
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    
    # Simple keyword-based classification
    yes_patterns = [
        r"\byes\b", r"\byeah\b", r"\byep\b", r"\bsure\b", r"\bok\b", r"\bokay\b",
        r"\bdone\b", r"\bcompleted\b", r"\bfinished\b", r"\bdid it\b"
    ]
    no_patterns = [
        r"\bno\b", r"\bnope\b", r"\bnot yet\b", r"\bdidn't\b", r"\bdid not\b",
        r"\bnot done\b", r"\bnot finished\b", r"\bnot completed\b"
    ]
    
    is_yes = any(re.search(p, normalized) for p in yes_patterns)
    is_no = any(re.search(p, normalized) for p in no_patterns)
    
    return is_yes, is_no

