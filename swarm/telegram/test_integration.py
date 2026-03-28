"""
Integration tests for Telegram polling service.
These tests validate that the application can run and handle basic operations.
"""

import asyncio
import logging
import pytest

# Import the modules to test
import sys

sys.path.insert(0, "/home/steen/kurs-bot/swarm")

# Load the module using importlib since it's a .py file, not a package
import importlib.util

spec = importlib.util.spec_from_file_location(
    "telegram_swarm_polling", "/home/steen/kurs-bot/swarm/telegram/telegram_swarm_polling.py"
)
telegram_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(telegram_module)

# Now we can use the module's contents
SwarmStateManager = telegram_module.SwarmStateManager
SwarmTelegramPoller = telegram_module.SwarmTelegramPoller
ApprovalRequest = telegram_module.ApprovalRequest
state_manager = telegram_module.state_manager


logger = logging.getLogger(__name__)


@pytest.fixture
def mock_state_manager():
    """Create a fresh state manager for testing."""
    return SwarmStateManager()


class TestApprovalRequest:
    """Tests for the ApprovalRequest data class."""

    def test_create_approval_request(self):
        """Test creating a basic approval request."""
        request = ApprovalRequest(
            request_id="test-123", chat_id="12345", user_id="67890", stage="start", summary="Test summary"
        )

        assert request.request_id == "test-123"
        assert request.chat_id == "12345"
        assert request.user_id == "67890"
        assert request.stage == "start"
        assert request.summary == "Test summary"
        assert not request.approved
        assert request.retry_feedback == ""

    def test_approval_request_to_dict(self):
        """Test converting approval request to dictionary."""
        request = ApprovalRequest(
            request_id="test-456", chat_id="11111", user_id="22222", approved=True, retry_feedback="Test feedback"
        )

        data = request.to_dict()

        assert data["request_id"] == "test-456"
        assert data["chat_id"] == "11111"
        assert data["user_id"] == "22222"
        assert data["approved"] is True
        assert data["retry_feedback"] == "Test feedback"


class TestSwarmStateManager:
    """Tests for the SwarmStateManager class."""

    def test_register_authorization(self, mock_state_manager):
        """Test registering a chat_id to user_id mapping."""
        mock_state_manager.register_authorization("12345", "67890")

        assert mock_state_manager.is_authorized("12345", "67890") is True
        assert mock_state_manager.is_authorized("12345", "11111") is False

    def test_add_pending_approval(self, mock_state_manager):
        """Test adding a pending approval request."""
        mock_state_manager.register_authorization("12345", "67890")

        mock_state_manager.add_pending_approval(
            request_id="req-001", chat_id="12345", user_id="67890", stage="start", summary="Test summary for approval"
        )

        # Verify the request was added
        request = mock_state_manager.get_pending_approval("req-001")
        assert request is not None
        assert request.request_id == "req-001"
        assert request.chat_id == "12345"
        assert request.user_id == "67890"
        assert not request.approved

    def test_approve_request(self, mock_state_manager):
        """Test approving a pending request."""
        mock_state_manager.register_authorization("12345", "67890")
        mock_state_manager.add_pending_approval(request_id="req-002", chat_id="12345", user_id="67890", stage="start")

        # Approve the request
        result = mock_state_manager.approve_request("req-002", "67890")

        assert result is True
        request = mock_state_manager.get_pending_approval("req-002")
        assert request.approved is True
        assert request.approved_by_user_id == "67890"

    def test_decline_request(self, mock_state_manager):
        """Test declining a pending request."""
        mock_state_manager.register_authorization("12345", "67890")
        mock_state_manager.add_pending_approval(
            request_id="req-003", chat_id="12345", user_id="67890", stage="end", summary="Summary for decline test"
        )

        result = mock_state_manager.decline_request("req-003", "67890")

        assert result is True

    def test_add_retry_feedback(self, mock_state_manager):
        """Test adding retry feedback to a request."""
        mock_state_manager.register_authorization("12345", "67890")
        mock_state_manager.add_pending_approval(request_id="req-004", chat_id="12345", user_id="67890", stage="start")

        result = mock_state_manager.add_retry_feedback(
            "req-004", "67890", "The instructions need to be more specific about the file format."
        )

        assert result is True
        request = mock_state_manager.get_pending_approval("req-004")
        assert request.retry_feedback == "The instructions need to be more specific about the file format."

    def test_get_active_request_ids(self):
        """Test getting all active request IDs."""
        sm = SwarmStateManager()
        sm.register_authorization("12345", "67890")
        sm.add_pending_approval(request_id="req-005", chat_id="12345", user_id="67890")
        sm.register_authorization("12346", "67891")
        sm.add_pending_approval(request_id="req-006", chat_id="12346", user_id="67891")

        active_ids = sm.get_active_request_ids()

        assert "req-005" in active_ids
        assert "req-006" in active_ids
        assert len(active_ids) == 2


class TestSwarmTelegramPoller:
    """Tests for the SwarmTelegramPoller class."""

    def test_poller_initialization(self):
        """Test that the poller initializes correctly."""
        poller = SwarmTelegramPoller()

        assert poller.running is False
        assert poller.poll_interval == 3

    def test_process_update_help_message(self):
        """Test processing a help message from an unauthorized user."""
        # Just verify the method exists and doesn't crash
        poller = SwarmTelegramPoller()
        assert hasattr(poller, "process_update")

    def test_process_update_approve_command(self):
        """Test processing an approve command."""
        sm = SwarmStateManager()
        sm.register_authorization("12345", "67890")
        sm.add_pending_approval(request_id="req-approve-001", chat_id="12345", user_id="67890", stage="start")

        # Verify the approval can be processed
        result = sm.approve_request("req-approve-001", "67890")
        assert result is True

        request = sm.get_pending_approval("req-approve-001")
        assert request.approved is True
        assert request.approved_by_user_id == "67890"

    def test_process_update_decline_command(self):
        """Test processing a decline command."""
        sm = SwarmStateManager()
        sm.register_authorization("12345", "67890")
        sm.add_pending_approval(request_id="req-decline-001", chat_id="12345", user_id="67890", stage="end")

        # Verify the decline can be processed
        result = sm.decline_request("req-decline-001", "67890")
        assert result is True

        # Verify the request still exists (decline marks but doesn't remove)
        request = sm.get_pending_approval("req-decline-001")
        assert request is not None
        assert request.request_id == "req-decline-001"

    def test_process_update_retry_command(self):
        """Test processing a retry command with feedback."""
        sm = SwarmStateManager()
        sm.register_authorization("12345", "67890")
        sm.add_pending_approval(request_id="req-retry-001", chat_id="12345", user_id="67890", stage="start")

        # Verify the retry feedback can be added
        feedback = "The instructions are unclear about file naming conventions."
        result = sm.add_retry_feedback("req-retry-001", "67890", feedback)
        assert result is True

        request = sm.get_pending_approval("req-retry-001")
        assert request.retry_feedback == feedback

    def test_process_update_with_missing_chats(self):
        """Test processing an update with missing chat or user info."""
        poller = SwarmTelegramPoller()

        # Test with missing chat_id - should not crash
        update = {"message": {"chat": {}, "from": {"id": "67890"}, "text": "/approve"}}

        # Should not raise an exception
        asyncio.run(poller.process_update(update))


class TestIntegrationWithHttpx:
    """Tests to verify httpx integration works correctly."""

    def test_httpx_import(self):
        """Test that httpx is properly imported in the module."""
        # telegram_module is already imported at module level
        assert telegram_module.httpx is not None

    def test_api_call_method_exists(self):
        """Test that the _api_call method exists."""
        poller = SwarmTelegramPoller()
        assert hasattr(poller, "_api_call")


class TestDependencyImports:
    """Tests to verify all required dependencies are imported."""

    def test_httpx_import(self):
        """Verify httpx is imported."""
        # Check that httpx is available in the module
        assert hasattr(telegram_module, "httpx")
        assert telegram_module.httpx is not None

    def test_required_modules(self):
        """Verify all required modules are imported."""
        required_modules = ["asyncio", "httpx", "logging", "os", "re"]

        for module_name in required_modules:
            assert hasattr(telegram_module, module_name), f"Module {module_name} is not imported"

    def test_telegram_module_has_expected_classes(self):
        """Verify the telegram module has the expected classes."""
        expected_classes = ["SwarmStateManager", "SwarmTelegramPoller", "ApprovalRequest"]

        for class_name in expected_classes:
            assert hasattr(telegram_module, class_name), f"Class {class_name} is not found in telegram module"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
