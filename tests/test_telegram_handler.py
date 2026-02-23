import pytest
from src.integrations.telegram import TelegramHandler, _markdown_to_html
from datetime import datetime

def test_parse_webhook_valid_message():
    payload = {
        "message": {
            "message_id": 123,
            "from": {"id": 42, "first_name": "John"},
            "text": "Hello!",
            "date": 1700000000
        }
    }
    result = TelegramHandler.parse_webhook(payload)
    assert result["user_id"] == "42"
    assert result["channel"] == "telegram"
    assert result["text"] == "Hello!"
    assert result["external_message_id"] == "123"
    assert isinstance(result["timestamp"], datetime)

def test_parse_webhook_ignores_bot_command():
    payload = {
        "message": {
            "message_id": 124,
            "from": {"id": 43, "first_name": "Bot"},
            "text": "/start",
            "date": 1700000001
        }
    }
    result = TelegramHandler.parse_webhook(payload)
    assert result is None

def test_parse_webhook_missing_text():
    payload = {
        "message": {
            "message_id": 125,
            "from": {"id": 44, "first_name": "NoText"},
            "date": 1700000002
        }
    }
    result = TelegramHandler.parse_webhook(payload)
    assert result is None

def test_parse_webhook_no_message():
    payload = {"update_id": 999}
    result = TelegramHandler.parse_webhook(payload)
    assert result is None

def test_parse_webhook_edited_message():
    payload = {
        "edited_message": {
            "message_id": 126,
            "from": {"id": 45, "first_name": "Edit"},
            "text": "Edited text",
            "date": 1700000003
        }
    }
    result = TelegramHandler.parse_webhook(payload)
    assert result["user_id"] == "45"
    assert result["text"] == "Edited text"
    assert result["external_message_id"] == "126"


def test_markdown_to_html_wraps_ascii_box_table_in_pre():
    text = (
        "Here is the summary:\n"
        "+-------+-------+\n"
        "| Name  | Score |\n"
        "+-------+-------+\n"
        "| Anna  | 10    |\n"
        "+-------+-------+"
    )
    rendered = _markdown_to_html(text)
    assert "<pre>" in rendered
    assert "</pre>" in rendered
    assert "| Name  | Score |" in rendered


def test_markdown_to_html_wraps_markdown_table_in_pre():
    text = "Name | Score\n--- | ---\nAnna | 10\nBen | 9"
    rendered = _markdown_to_html(text)
    assert "<pre>" in rendered
    assert "Name | Score" in rendered


def test_markdown_to_html_does_not_wrap_single_pipe_sentence():
    text = "Use A | B when comparing two options."
    rendered = _markdown_to_html(text)
    assert "<pre>" not in rendered
