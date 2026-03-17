"""Unit tests for UserFactory test utility."""

from sqlalchemy.orm import Session

from src.memories import MemoryManager


class TestUserFactory:
    """Tests for UserFactory test utility."""

    def test_factory_creates_user(self, db_session: Session, user_factory):
        """UserFactory should create user with custom attributes."""
        user = user_factory.create(external_id="custom_123", first_name="Custom", language="es")

        assert user.external_id == "custom_123"
        assert user.first_name == "Custom"

        # Check language memory was created
        mm = MemoryManager(db_session)
        lang = mm.get_memory(user.user_id, "user_language")
        assert lang[0]["value"] == "es"

    def test_factory_creates_ready_user(self, db_session: Session, user_factory):
        """UserFactory should create ready user with onboarding complete."""
        user = user_factory.create_ready_user(external_id="ready_123", first_name="Ready")

        # Verify user has expected attributes
        assert user.external_id == "ready_123"
        assert user.first_name == "Ready"
        assert user.timezone == "Europe/Oslo"  # Ready users are assumed Europe/Oslo

        # Verify memories were created
        mm = MemoryManager(db_session)
        consent = mm.get_memory(user.user_id, "data_consent")
        assert consent
