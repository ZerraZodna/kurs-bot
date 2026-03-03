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
