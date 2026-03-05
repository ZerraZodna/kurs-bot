"""Status checking logic for onboarding flow."""

from __future__ import annotations

from typing import Any, Dict, Optional


def get_onboarding_status_dict(
    has_name: bool,
    has_consent: bool,
    declined_consent: bool = False,
) -> Dict[str, Any]:
    """
    Build onboarding status dictionary for minimal onboarding.

    Required onboarding:
    - name
    - consent
    """
    steps_completed = []
    if has_name:
        steps_completed.append("name")
    if has_consent:
        steps_completed.append("consent")

    next_step = None
    if not has_name:
        next_step = "name"
    elif not has_consent:
        next_step = "consent"

    onboarding_complete = has_name and has_consent

    return {
        "has_name": has_name,
        "has_consent": has_consent,
        "onboarding_complete": onboarding_complete,
        "steps_completed": steps_completed,
        "next_step": next_step,
        "declined_consent": declined_consent,
    }
