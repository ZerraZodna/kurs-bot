from __future__ import annotations

from typing import Any, Dict, Optional
import re


def detect_commitment_keywords(message: str) -> bool:
    message_lower = message.lower()
    commitment_keywords = [
        "yes",
        "yeah",
        "sure",
        "ready",
        "let's do it",
        "i'm in",
        "commit",
        "start",
        "begin",
        "sign me up",
        "i want to",
        "interested",
        "absolutely",
        "definitely",
        "ok",
        "okay",
        # Norwegian
        "ja",
        "jada",
        "klar",
        "begynn",
        "start",
        "vil gjerne",
        # Swedish
        "ja",
        "gärna",
        "redo",
        "börja",
        # Danish
        "ja",
        "gerne",
        "klar",
        "begynd",
        # German
        "ja",
        "klar",
        "bereit",
        "los geht's",
        # Spanish
        "sí",
        "si",
        "claro",
        "listo",
        "empecemos",
        "quiero",
        # French
        "oui",
        "d'accord",
        "prêt",
        "prete",
        "commençons",
        "commencer",
        # Portuguese
        "sim",
        "claro",
        "pronto",
        "vamos começar",
        "quero",
        # Italian
        "sì",
        "si",
        "certo",
        "pronto",
        "iniziamo",
        "voglio",
    ]
    return any(keyword in message_lower for keyword in commitment_keywords)


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


def detect_schedule_request(message: str) -> bool:
    message_lower = message.lower()
    schedule_keywords = [
        "remind",
        "reminder",
        "schedule",
        "daily",
        "every day",
        "send me",
        "notify",
        "notification",
        "alert",
        "ping",
        # Norwegian
        "påminn",
        "minne",
        "hver dag",
        "daglig",
        "varsle",
    ]
    return any(keyword in message_lower for keyword in schedule_keywords)


def handle_lesson_status_response(text: str) -> Dict[str, Any]:
    text_lower = text.lower().strip()

    new_keywords = [
        "new",
        "ny",
        "beginner",
        "nybegynner",
        "start",
        "beginning",
        "never",
        "aldri",
        "first time",
        "første gang",
    ]
    is_new = any(kw in text_lower for kw in new_keywords)

    continuing_keywords = [
        "continuing",
        "fortsetter",
        "already",
        "allerede",
        "started",
        "begynt",
        "on lesson",
        "på leksjon",
        "lesson",
        "leksjon",
    ]
    is_continuing = any(kw in text_lower for kw in continuing_keywords)

    lesson_match = re.search(r"(?:lesson|leksjon)\s*(\d+)", text_lower)
    if lesson_match:
        lesson_num = int(lesson_match.group(1))
        if 1 <= lesson_num <= 365:
            return {"action": "send_specific_lesson", "lesson_id": lesson_num}

    if is_new:
        return {"action": "send_lesson_1"}
    if is_continuing:
        return {"action": "ask_lesson_number"}

    return {"action": "clarify"}
