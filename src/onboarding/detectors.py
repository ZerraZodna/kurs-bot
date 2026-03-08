from __future__ import annotations

from typing import Any, Dict, Optional
import re


def detect_decline_keywords(message: str) -> bool:
    message_lower = message.lower()
    decline_keywords = [
        "no",
        "not interested",
        "no thanks",
        "no thank you",
        "stop",
        "don't want",
        "do not want",
        "not into",
        "leave me",
        # Norwegian
        "nei",
        "ikke interessert",
        "nei takk",
        "stopp",
        "vil ikke",
        "ønsker ikke",
    ]
    return any(keyword in message_lower for keyword in decline_keywords)


def detect_consent_keywords(message: str) -> Optional[bool]:
    message_lower = message.lower()
    yes_keywords = [
        "yes",
        "yeah",
        "sure",
        "ok",
        "okay",
        "i agree",
        "consent",
        # Norwegian
        "ja",
        "jada",
        "greit",
        "ok",
        "samtykker",
    ]
    no_keywords = [
        "no",
        "no thanks",
        "no thank you",
        "don't",
        "do not",
        # Norwegian
        "nei",
        "nei takk",
        "ikke",
    ]
    if any(k in message_lower for k in yes_keywords):
        return True
    if any(k in message_lower for k in no_keywords):
        return False
    return None
