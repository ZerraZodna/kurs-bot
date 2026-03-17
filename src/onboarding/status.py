"""Status checking logic for onboarding flow."""

from __future__ import annotations

from typing import Any, Dict


def get_onboarding_status_dict(
    has_consent: bool,
    declined_consent: bool = False,
) -> Dict[str, Any]:
    """
    Build onboarding status dictionary for minimal onboarding.

    Required onboarding:
    - consent (name is now skipped - using Telegram name from DB)
    """
    steps_completed = []
    # Name is now automatically considered complete (using Telegram name)
    steps_completed.append("name")
    if has_consent:
        steps_completed.append("consent")

    next_step = None
    # Only require consent - name step is skipped
    if not has_consent:
        next_step = "consent"

    # Onboarding complete when consent is given (name always True from Telegram)
    onboarding_complete = has_consent

    return {
        "has_name": True,  # Always True - using Telegram name
        "has_consent": has_consent,
        "onboarding_complete": onboarding_complete,
        "steps_completed": steps_completed,
        "next_step": next_step,
        "declined_consent": declined_consent,
    }
