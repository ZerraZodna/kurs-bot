import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_reply_chat_id(parsed_update: dict[str, Any]) -> int | None:
    """
    Enforce same-chat reply policy:
    - If inbound came from a group/supergroup, reply in that same group chat.
    - If inbound came from private chat, reply in that same private chat.
    - No mention requirements or runtime mode switches.
    """
    raw_chat_id = parsed_update.get("chat_id")
    if raw_chat_id is None:
        logger.warning("[telegram routing] missing chat_id in parsed update")
        return None

    try:
        chat_id = int(raw_chat_id)
    except (TypeError, ValueError):
        logger.warning("[telegram routing] invalid chat_id=%r", raw_chat_id)
        return None

    chat_type = str(parsed_update.get("chat_type") or "unknown")
    logger.info(
        "[telegram routing] inbound_chat_type=%s inbound_chat_id=%s resolved_chat_id=%s",
        chat_type,
        raw_chat_id,
        chat_id,
    )
    return chat_id
