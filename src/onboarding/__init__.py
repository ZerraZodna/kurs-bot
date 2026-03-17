"""Top-level onboarding package.

Provides onboarding detectors, prompts, flow, schedule setup, and
user-management utilities.
"""
from . import detectors, flow, schedule_setup, status, user_management
from .service import OnboardingService

__all__ = [
    "detectors",
    "flow",
    "schedule_setup",
    "status",
    "user_management",
    "OnboardingService",
]
