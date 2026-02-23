from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.models.database import TriggerEmbedding, User
from src.services.admin_notifier import get_admin_chat_id
from src.services.embedding_service import get_embedding_service
from src.triggers.trigger_matcher import refresh_trigger_matcher_cache

logger = logging.getLogger(__name__)


def _is_trigger_admin(session: Session, user_id: int) -> bool:
    """Authorize trigger-management commands for the configured Telegram admin."""
    if session is None:
        return False
    admin_chat_id = get_admin_chat_id()
    if admin_chat_id is None:
        return False

    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        return False
    return (user.channel or "").lower() == "telegram" and str(user.external_id) == str(admin_chat_id)


def _trigger_admin_help() -> str:
    return (
        "Trigger admin commands:\n"
        "- trigger_add <action_type> | <phrase> | <threshold_optional>\n"
        "- trigger_list [action_type]\n"
        "- trigger_delete <trigger_id>"
    )


async def handle_trigger_admin_commands(
    text: str,
    session: Session,
    user_id: int,
) -> Optional[str]:
    """Admin-only trigger management commands exposed via Telegram chat."""
    raw = (text or "").strip()
    lower = raw.lower()

    is_trigger_cmd = (
        lower.startswith("trigger_add")
        or lower.startswith("trigger_list")
        or lower.startswith("trigger_delete")
    )
    if not is_trigger_cmd:
        return None

    if not _is_trigger_admin(session, user_id):
        return "This command is admin-only."

    if lower == "trigger_add" or lower.startswith("trigger_add "):
        payload = raw[len("trigger_add") :].strip()
        if not payload:
            return _trigger_admin_help()

        parts = [p.strip() for p in payload.split("|")]
        if len(parts) < 2:
            return _trigger_admin_help()

        action_type = (parts[0] or "").strip().lower()
        phrase = (parts[1] or "").strip()
        if not action_type or not phrase:
            return _trigger_admin_help()

        threshold = float(settings.TRIGGER_SIMILARITY_THRESHOLD)
        if len(parts) >= 3 and parts[2]:
            try:
                threshold = float(parts[2])
            except Exception:
                return "Invalid threshold. Use a float between 0.0 and 1.0."
        if threshold < 0.0 or threshold > 1.0:
            return "Invalid threshold. Use a float between 0.0 and 1.0."

        action_exists = (
            session.query(TriggerEmbedding.id)
            .filter(TriggerEmbedding.action_type == action_type)
            .first()
            is not None
        )
        if not action_exists:
            actions = (
                session.query(TriggerEmbedding.action_type)
                .distinct()
                .order_by(TriggerEmbedding.action_type.asc())
                .all()
            )
            supported = ", ".join(a[0] for a in actions) if actions else "-"
            return f"Unknown action_type '{action_type}'. Existing actions: {supported}"

        emb_svc = get_embedding_service()
        embedding = await emb_svc.generate_embedding(phrase)
        if not embedding:
            return "Failed to generate embedding for phrase. Check embedding backend availability."

        row = TriggerEmbedding(
            name=f"{action_type}_admin",
            action_type=action_type,
            embedding=emb_svc.embedding_to_bytes(embedding),
            threshold=float(threshold),
        )
        try:
            session.add(row)
            session.commit()
            refresh_trigger_matcher_cache()
            return (
                f"Added trigger id={row.id} action_type={action_type} "
                f"threshold={float(threshold):.2f} phrase=\"{phrase}\""
            )
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            logger.exception("Failed adding trigger embedding: %s", e)
            return "Failed to add trigger embedding."

    if lower == "trigger_list" or lower.startswith("trigger_list "):
        action_filter = raw[len("trigger_list") :].strip().lower()
        q = session.query(TriggerEmbedding)
        if action_filter:
            q = q.filter(TriggerEmbedding.action_type == action_filter)

        rows = q.order_by(TriggerEmbedding.id.desc()).limit(50).all()
        if not rows:
            if action_filter:
                return f"No trigger embeddings found for action_type '{action_filter}'."
            return "No trigger embeddings found."

        lines = [f"Trigger embeddings ({len(rows)} shown):"]
        for r in rows:
            lines.append(
                f"id={r.id} action={r.action_type} threshold={float(r.threshold or 0.0):.2f} name={r.name}"
            )
        if len(rows) == 50:
            lines.append("Showing latest 50 entries.")
        return "\n".join(lines)

    if lower == "trigger_delete" or lower.startswith("trigger_delete "):
        payload = raw[len("trigger_delete") :].strip()
        if not payload:
            return _trigger_admin_help()
        try:
            trigger_id = int(payload)
        except Exception:
            return "Usage: trigger_delete <trigger_id>"

        row = (
            session.query(TriggerEmbedding)
            .filter(TriggerEmbedding.id == trigger_id)
            .first()
        )
        if not row:
            return f"Trigger id={trigger_id} not found."

        action = row.action_type
        try:
            session.delete(row)
            session.commit()
            refresh_trigger_matcher_cache()
            return f"Deleted trigger id={trigger_id} action_type={action}."
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            logger.exception("Failed deleting trigger embedding: %s", e)
            return "Failed to delete trigger embedding."

    return None
