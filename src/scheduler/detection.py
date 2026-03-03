"""
Schedule Intent Detection.

This module handles detection of schedule-related intents in user messages.
"""

from __future__ import annotations


def detect_schedule_request(message: str) -> bool:
    """
    Detect if a message contains schedule/reminder keywords.
    
    This function identifies when a user is asking to set up, modify,
    or query schedules and reminders.
    
    Args:
        message: The user message to check
        
    Returns:
        True if the message appears to be a schedule request
        
    Examples:
        >>> detect_schedule_request("Can you remind me every day at 7am?")
        True
        >>> detect_schedule_request("What is my schedule?")
        True
        >>> detect_schedule_request("Tell me about lesson 5")
        False
    """
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
