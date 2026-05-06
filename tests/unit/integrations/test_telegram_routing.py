"""Unit tests for telegram_routing — verify same-chat reply policy."""

from src.integrations.telegram_routing import resolve_reply_chat_id


class TestResolveReplyChatId:
    """Verify resolve_reply_chat_id returns the correct chat_id."""

    def test_group_inbound_returns_group_chat_id(self):
        parsed = {"chat_id": "-1001234567890", "chat_type": "supergroup"}
        assert resolve_reply_chat_id(parsed) == -1001234567890

    def test_private_inbound_returns_private_chat_id(self):
        parsed = {"chat_id": "123456789", "chat_type": "private"}
        assert resolve_reply_chat_id(parsed) == 123456789

    def test_missing_chat_id_returns_none(self):
        parsed = {"chat_type": "private"}
        assert resolve_reply_chat_id(parsed) is None

    def test_invalid_chat_id_returns_none(self):
        parsed = {"chat_id": "not_a_number", "chat_type": "private"}
        assert resolve_reply_chat_id(parsed) is None

    def test_unknown_chat_type_returns_chat_id(self):
        parsed = {"chat_id": "999", "chat_type": "unknown"}
        assert resolve_reply_chat_id(parsed) == 999

    def test_chat_id_as_int(self):
        parsed = {"chat_id": 42, "chat_type": "private"}
        assert resolve_reply_chat_id(parsed) == 42
