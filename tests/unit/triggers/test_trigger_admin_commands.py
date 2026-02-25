"""
Unit tests for Trigger Admin Commands.

Migrated from tests/test_trigger_admin_commands.py to use new test fixtures.
"""

import pytest

from src.models.database import User, TriggerEmbedding
from src.services.dialogue.admin_handler import handle_trigger_admin_commands


class DummyEmbedSvc:
    """Dummy embedding service for testing."""
    async def generate_embedding(self, text: str):
        return [0.1, 0.2, 0.3, 0.4]

    def embedding_to_bytes(self, emb):
        import numpy as np

        return np.array(emb, dtype="float32").tobytes()


def _seed_users_and_action(session, admin_user_id):
    """Seed test users and trigger action."""
    other_user = User(external_id="222", channel="telegram", opted_in=True)
    session.add(other_user)
    session.commit()
    session.add(
        TriggerEmbedding(
            name="create_schedule_seed",
            action_type="create_schedule",
            embedding=DummyEmbedSvc().embedding_to_bytes([1.0, 0.0, 0.0, 0.0]),
            threshold=0.75,
        )
    )
    session.commit()
    return other_user.user_id


class TestTriggerAdminCommands:
    """Test suite for trigger admin commands."""

    @pytest.mark.asyncio
    async def test_trigger_add_requires_admin(self, db_session):
        """Given: A non-admin user trying to add a trigger
        When: Calling trigger_add command
        Then: Should return 'This command is admin-only.' and not add the trigger."""
        # Get initial count of triggers (from seed)
        initial_count = db_session.query(TriggerEmbedding).filter_by(action_type="create_schedule").count()
        
        # Create admin user with external_id 111 (matching the original test)
        admin_user = User(external_id="111", channel="telegram", opted_in=True)
        db_session.add(admin_user)
        db_session.commit()
        
        other_user = User(external_id="222", channel="telegram", opted_in=True)
        db_session.add(other_user)
        db_session.commit()

        import unittest.mock as mock
        with mock.patch("src.services.dialogue.admin_handler.get_admin_chat_id", return_value="111"):
            with mock.patch("src.services.dialogue.admin_handler.get_embedding_service", return_value=DummyEmbedSvc()):
                out = await handle_trigger_admin_commands(
                    text="trigger_add create_schedule | remind me daily | 0.6",
                    session=db_session,
                    user_id=other_user.user_id,
                )
        assert out == "This command is admin-only."

        # Verify no new trigger was added (count should be the same)
        final_count = db_session.query(TriggerEmbedding).filter_by(action_type="create_schedule").count()
        assert final_count == initial_count

    @pytest.mark.asyncio
    async def test_trigger_add_admin_allowed(self, db_session):
        """Given: An admin user adding a trigger
        When: Calling trigger_add command
        Then: Should successfully add the trigger."""
        # Create admin user with external_id 111
        admin_user = User(external_id="111", channel="telegram", opted_in=True)
        db_session.add(admin_user)
        db_session.commit()

        import unittest.mock as mock
        with mock.patch("src.services.dialogue.admin_handler.get_admin_chat_id", return_value="111"):
            with mock.patch("src.services.dialogue.admin_handler.get_embedding_service", return_value=DummyEmbedSvc()):
                out_admin = await handle_trigger_admin_commands(
                    text="trigger_add create_schedule | remind me daily | 0.6",
                    session=db_session,
                    user_id=admin_user.user_id,
                )
        assert "Added trigger id=" in out_admin

    @pytest.mark.asyncio
    async def test_trigger_add_list_delete_roundtrip(self, db_session):
        """Given: An admin user performing add, list, delete operations
        When: Performing full CRUD cycle on triggers
        Then: Should add, list, and delete triggers correctly."""
        # Create admin user with external_id 111
        admin_user = User(external_id="111", channel="telegram", opted_in=True)
        db_session.add(admin_user)
        db_session.commit()

        import unittest.mock as mock
        with mock.patch("src.services.dialogue.admin_handler.get_admin_chat_id", return_value="111"):
            with mock.patch("src.services.dialogue.admin_handler.get_embedding_service", return_value=DummyEmbedSvc()):
                # Add
                add_out = await handle_trigger_admin_commands(
                    text="trigger_add create_schedule | remind me after lunch | 0.66",
                    session=db_session,
                    user_id=admin_user.user_id,
                )
                assert "Added trigger id=" in add_out
                assert "threshold=0.66" in add_out

                # List
                list_out = await handle_trigger_admin_commands(
                    text="trigger_list create_schedule",
                    session=db_session,
                    user_id=admin_user.user_id,
                )
                assert list_out is not None
                assert "Trigger embeddings" in list_out
                assert "action=create_schedule" in list_out
                assert "remind me after lunch" in list_out

                # Get latest trigger
                latest = (
                    db_session.query(TriggerEmbedding)
                    .filter(TriggerEmbedding.action_type == "create_schedule")
                    .order_by(TriggerEmbedding.id.desc())
                    .first()
                )
                assert latest is not None

                # Delete
                del_out = await handle_trigger_admin_commands(
                    text=f"trigger_delete {latest.id}",
                    session=db_session,
                    user_id=admin_user.user_id,
                )
                assert del_out == f"Deleted trigger id={latest.id} action_type=create_schedule."

                # Verify deleted
                deleted = (
                    db_session.query(TriggerEmbedding)
                    .filter(TriggerEmbedding.id == latest.id)
                    .first()
                )
                assert deleted is None

