"""Status checking logic for onboarding flow."""

from __future__ import annotations

from typing import Any, Dict, Optional


def get_onboarding_status_dict(
    has_name: bool,
    has_consent: bool,
    has_commitment: bool,
    has_lesson_status: bool,
    has_timezone: bool = False,
    declined_commitment: bool = False,
    declined_consent: bool = False,
) -> Dict[str, Any]:
    """
    Build onboarding status dictionary.
    
    Args:
        has_name: User provided name
        has_consent: User gave data consent
        has_commitment: User committed to ACIM
        has_lesson_status: User stated their lesson status
        has_timezone: User has timezone set (optional, defaults to False for backward compatibility)
        declined_commitment: User declined ACIM
        declined_consent: User declined consent
    
    Returns:
        Dictionary with onboarding status
    """
    steps_completed = []
    if has_name:
        steps_completed.append("name")
    if has_consent:
        steps_completed.append("consent")
    if has_timezone:
        steps_completed.append("timezone")
    if has_commitment:
        steps_completed.append("commitment")
    if has_lesson_status:
        steps_completed.append("lesson_status")

    next_step = None
    if not has_name:
        next_step = "name"
    elif not has_consent:
        next_step = "consent"
    elif not has_timezone:
        next_step = "timezone"
    elif not has_commitment:
        next_step = "commitment"
    elif not has_lesson_status:
        next_step = "lesson_status"

    onboarding_complete = (
        has_name and has_timezone and has_consent and has_commitment and has_lesson_status
    )

    return {
        "has_name": has_name,
        "has_timezone": has_timezone,
        "has_consent": has_consent,
        "has_commitment": has_commitment,
        "has_lesson_status": has_lesson_status,
        "onboarding_complete": onboarding_complete,
        "steps_completed": steps_completed,
        "next_step": next_step,
        "declined_commitment": declined_commitment,
        "declined_consent": declined_consent,
    }
