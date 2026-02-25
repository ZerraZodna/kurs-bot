"""Unit tests for onboarding fact extraction.

Migrated from tests/test_onboarding_fact_extraction.py to use new test fixtures.
"""

import pytest
from src.onboarding.detectors import handle_lesson_status_response


class TestOnboardingFactExtraction:
    """Tests for onboarding fact extraction."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("I am on lesson 6", {"action": "send_specific_lesson", "lesson_id": 6}),
            ("Continuing from lesson 3", {"action": "send_specific_lesson", "lesson_id": 3}),
            ("new here, first time", {"action": "send_lesson_1"}),
            ("I'm new", {"action": "send_lesson_1"}),
            ("I have done the course before", {"action": "ask_lesson_number"}),
            ("I've completed the course", {"action": "ask_lesson_number"}),
            ("I've already started", {"action": "ask_lesson_number"}),
            ("on lesson 12", {"action": "send_specific_lesson", "lesson_id": 12}),
            ("not sure", {"action": "clarify"}),
        ],
    )
    def test_handle_lesson_status_responses(self, text, expected):
        """Given: Various lesson status responses
        When: Parsing the response
        Then: Should extract correct action and lesson_id
        """
        out = handle_lesson_status_response(text)
        assert out["action"] == expected["action"]
        if "lesson_id" in expected:
            assert out.get("lesson_id") == expected["lesson_id"]

