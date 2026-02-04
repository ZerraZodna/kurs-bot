"""Pause/stop lesson delivery detection."""

from __future__ import annotations


def detect_pause_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False

    pause_terms = (
        "pause",
        "stop",
        "cancel",
        "halt",
        "disable",
        "hold",
        "turn off",
        "switch off",
        "stopp",
        "stoppe",
        "avslutt",
        "kanseller",
        "sett på pause",
        "skru av",
        "slå av",
        "deaktiver",
        "stans",
    )

    target_terms = (
        "lesson",
        "lessons",
        "daily",
        "reminder",
        "reminders",
        "schedule",
        "plan",
        "leksjon",
        "leksjoner",
        "påminnelse",
        "påminnelser",
    )

    if any(term in normalized for term in pause_terms) and any(term in normalized for term in target_terms):
        return True

    short_commands = {
        "pause",
        "stop",
        "cancel",
        "turn off reminders",
        "turn off reminder",
        "disable reminders",
        "disable reminder",
        "pause reminders",
        "stop reminders",
        "pause lessons",
        "stop lessons",
        "stopp",
        "skru av påminnelser",
        "skru av påminnelse",
        "slå av påminnelser",
        "slå av påminnelse",
        "pause leksjoner",
        "stopp leksjoner",
        "pause påminnelser",
        "stopp påminnelser",
    }

    return normalized in short_commands
