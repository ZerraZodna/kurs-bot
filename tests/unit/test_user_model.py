"""Unit tests for User model.

Refactored to use new test fixtures from tests/fixtures/
"""

from sqlalchemy.orm import Session

from src.models.database import User


class TestUserModel:
    """Test suite for User model CRUD operations."""

    def test_user_crud(self, db_session: Session):
        """Should create, read, update, and delete users."""
        # When: Creating a user
        user = User(
            external_id="12345",
            channel="telegram",
            first_name="Test",
            last_name="User",
            opted_in=True,
        )
        db_session.add(user)
        db_session.commit()

        # Then: User should have an ID
        assert user.user_id is not None

        # When: Reading the user
        fetched = db_session.query(User).filter_by(external_id="12345").first()

        # Then: User should exist with correct data
        assert fetched is not None
        assert fetched.first_name == "Test"

        # When: Updating the user
        fetched.first_name = "Updated"
        db_session.commit()
        updated = db_session.query(User).filter_by(user_id=user.user_id).first()

        # Then: Update should be reflected
        assert updated.first_name == "Updated"

        # When: Deleting the user
        db_session.delete(updated)
        db_session.commit()

        # Then: User should no longer exist
        assert db_session.query(User).filter_by(user_id=user.user_id).first() is None
