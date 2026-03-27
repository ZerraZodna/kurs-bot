from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, cast

from sqlalchemy.orm import Session

from src.core.timezone import utc_now as _utc_now
from src.memories.memory_handler import MemoryHandler
from src.memories.user_data_service import delete_user_content_rows
from src.models.database import (
    ConsentLog,
    GdprAuditLog,
    GdprRequest,
    MessageLog,
    Schedule,
    Unsubscribe,
    User,
)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_consent(
    session: Session,
    user_id: int,
    scope: str,
    granted: bool,
    source: str,
    consent_version: str | None = None,
) -> ConsentLog:
    consent = ConsentLog(
        user_id=user_id,
        scope=scope,
        granted=granted,
        consent_version=consent_version,
        source=source,
        created_at=_utc_now(),
    )
    session.add(consent)
    session.commit()
    return consent


def record_gdpr_request(
    session: Session,
    user_id: int | None,
    request_type: str,
    status: str,
    actor: str,
    reason: str | None = None,
    details: Dict[str, Any] | None = None,
) -> GdprRequest:
    request = GdprRequest(
        user_id=user_id,
        request_type=request_type,
        status=status,
        reason=reason,
        details=json.dumps(details or {}),
        actor=actor,
        requested_at=_utc_now(),
        processed_at=_utc_now(),
    )
    session.add(request)
    session.commit()
    return request


def record_gdpr_audit(
    session: Session,
    user_id: int | None,
    action: str,
    actor: str,
    details: Dict[str, Any] | None = None,
) -> GdprAuditLog:
    audit = GdprAuditLog(
        user_id=user_id,
        action=action,
        actor=actor,
        details=json.dumps(details or {}),
        created_at=_utc_now(),
    )
    session.add(audit)
    session.commit()
    return audit


def export_user_data(session: Session, user_id: int) -> Dict[str, Any]:
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)

    memory_handler = MemoryHandler(session)
    memories = [cast(Any, m) for m in memory_handler.list_user_memories(user_id=user_id)]
    schedules = [cast(Any, s) for s in session.query(Schedule).filter_by(user_id=user_id).all()]
    messages = [cast(Any, m) for m in session.query(MessageLog).filter_by(user_id=user_id).all()]
    unsubscribes = [cast(Any, u) for u in session.query(Unsubscribe).filter_by(user_id=user_id).all()]
    consent_logs = [cast(Any, c) for c in session.query(ConsentLog).filter_by(user_id=user_id).all()]
    gdpr_requests = [cast(Any, r) for r in session.query(GdprRequest).filter_by(user_id=user_id).all()]
    gdpr_audits = [cast(Any, a) for a in session.query(GdprAuditLog).filter_by(user_id=user_id).all()]

    return {
        "schema_version": 1,
        "exported_at": _utc_now().isoformat(),
        "user": {
            "user_id": user.user_id,
            "external_id": user.external_id,
            "channel": user.channel,
            "phone_number": user.phone_number,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "opted_in": user.opted_in,
            "processing_restricted": user.processing_restricted,
            "restriction_reason": user.restriction_reason,
            "is_deleted": user.is_deleted,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
        },
        "memories": [
            {
                "memory_id": m.memory_id,
                "category": m.category,
                "key": m.key,
                "value": m.value,
                "source": m.source,
                "is_active": m.is_active,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                "archived_at": m.archived_at.isoformat() if m.archived_at else None,
            }
            for m in memories
        ],
        "schedules": [
            {
                "schedule_id": s.schedule_id,
                "lesson_id": s.lesson_id,
                "schedule_type": s.schedule_type,
                "cron_expression": s.cron_expression,
                "next_send_time": s.next_send_time.isoformat() if s.next_send_time else None,
                "last_sent_at": s.last_sent_at.isoformat() if s.last_sent_at else None,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in schedules
        ],
        "message_logs": [
            {
                "message_id": m.message_id,
                "direction": m.direction,
                "channel": m.channel,
                "external_message_id": m.external_message_id,
                "content": m.content,
                "status": m.status,
                "error_message": m.error_message,
                "conversation_thread_id": m.conversation_thread_id,
                "message_role": m.message_role,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "processed_at": m.processed_at.isoformat() if m.processed_at else None,
            }
            for m in messages
        ],
        "unsubscribes": [
            {
                "unsubscribe_id": u.unsubscribe_id,
                "channel": u.channel,
                "reason": u.reason,
                "unsubscribed_at": u.unsubscribed_at.isoformat() if u.unsubscribed_at else None,
                "compliance_required": u.compliance_required,
            }
            for u in unsubscribes
        ],
        "consent_logs": [
            {
                "consent_id": c.consent_id,
                "scope": c.scope,
                "granted": c.granted,
                "consent_version": c.consent_version,
                "source": c.source,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in consent_logs
        ],
        "gdpr_requests": [
            {
                "request_id": r.request_id,
                "request_type": r.request_type,
                "status": r.status,
                "reason": r.reason,
                "details": r.details,
                "actor": r.actor,
                "requested_at": r.requested_at.isoformat() if r.requested_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            }
            for r in gdpr_requests
        ],
        "gdpr_audit_logs": [
            {
                "audit_id": a.audit_id,
                "action": a.action,
                "details": a.details,
                "actor": a.actor,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in gdpr_audits
        ],
    }


def restrict_processing(
    session: Session,
    user_id: int,
    reason: str | None,
    actor: str,
) -> None:
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)

    user.processing_restricted = True
    user.opted_in = False
    user.restriction_reason = reason
    session.add(user)
    session.commit()

    record_gdpr_request(
        session=session,
        user_id=user_id,
        request_type="restrict",
        status="completed",
        actor=actor,
        reason=reason,
    )
    record_gdpr_audit(
        session=session,
        user_id=user_id,
        action="restrict",
        actor=actor,
        details={"reason": reason},
    )


def object_to_processing(
    session: Session,
    user_id: int,
    reason: str | None,
    actor: str,
) -> None:
    """Handle GDPR right to object by restricting processing."""
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)

    user.processing_restricted = True
    user.opted_in = False
    user.restriction_reason = reason or "object"
    session.add(user)
    session.commit()

    record_gdpr_request(
        session=session,
        user_id=user_id,
        request_type="object",
        status="completed",
        actor=actor,
        reason=reason,
    )
    record_gdpr_audit(
        session=session,
        user_id=user_id,
        action="object",
        actor=actor,
        details={"reason": reason},
    )


def withdraw_consent(
    session: Session,
    user_id: int,
    scope: str,
    actor: str,
    reason: str | None = None,
) -> None:
    """Withdraw consent for a scope and restrict processing."""
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)

    user.opted_in = False
    user.processing_restricted = True
    user.restriction_reason = reason or "consent_withdrawn"
    session.add(user)
    session.commit()

    record_consent(
        session=session,
        user_id=user_id,
        scope=scope,
        granted=False,
        source="gdpr_withdrawal",
    )
    record_gdpr_request(
        session=session,
        user_id=user_id,
        request_type="withdraw_consent",
        status="completed",
        actor=actor,
        reason=reason,
        details={"scope": scope},
    )
    record_gdpr_audit(
        session=session,
        user_id=user_id,
        action="withdraw_consent",
        actor=actor,
        details={"scope": scope, "reason": reason},
    )


def rectify_user(
    session: Session,
    user_id: int,
    updates: Dict[str, Any],
    memory_updates: List[Dict[str, Any]] | None,
    actor: str,
) -> None:
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)
    memory_handler = MemoryHandler(session)

    allowed_fields = {"first_name", "last_name", "email", "phone_number"}
    for field, value in updates.items():
        if field in allowed_fields:
            setattr(user, field, value)

    if memory_updates:
        for update in memory_updates:
            memory_id = update.get("memory_id")
            value = update.get("value")
            if memory_id is None or value is None:
                continue
            memory = memory_handler.get_user_memory_by_id(user_id=user_id, memory_id=memory_id)
            if memory:
                memory = cast(Any, memory)
                memory.value = value
                memory.value_hash = _hash_value(value)
                memory.updated_at = _utc_now()
                session.add(memory)

    session.add(user)
    session.commit()

    record_gdpr_request(
        session=session,
        user_id=user_id,
        request_type="rectify",
        status="completed",
        actor=actor,
        details={"updates": updates, "memory_updates": memory_updates or []},
    )
    record_gdpr_audit(
        session=session,
        user_id=user_id,
        action="rectify",
        actor=actor,
        details={"updates": updates, "memory_updates": memory_updates or []},
    )


def erase_user_data(
    session: Session,
    user_id: int,
    reason: str | None,
    actor: str,
) -> None:
    from src.services.admin_notifier import send_admin_notification

    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)

    name = " ".join([n for n in [user.first_name, user.last_name] if n]) or str(user_id)

    deleted_metrics = delete_user_content_rows(session, user_id)

    user.first_name = None
    user.last_name = None
    user.email = None
    user.phone_number = None
    user.external_id = f"deleted-{user_id}"
    user.channel = "deleted"
    user.opted_in = False
    user.processing_restricted = True
    user.is_deleted = True
    user.deleted_at = _utc_now()
    session.add(user)
    session.commit()

    send_admin_notification(f"[INFO] User left: {name} (reason: GDPR exit).")

    record_gdpr_request(
        session=session,
        user_id=user_id,
        request_type="erase",
        status="completed",
        actor=actor,
        reason=reason,
    )
    record_gdpr_audit(
        session=session,
        user_id=user_id,
        action="erase",
        actor=actor,
        details={"reason": reason, **deleted_metrics},
    )


def clean_user_data(
    session: Session,
    user_id: int,
    reason: str | None,
    actor: str,
) -> None:
    """Erase user PII and records like `erase_user_data` but keep the
    user account record active so the same `user_id` can be reused by tests
    or the WebUI. Performs the same deletion/anonymization steps and then
    re-activates the DB `User` row.

    IMPORTANT: This intentionally differs from `erase_user_data` by leaving
    the `User` row active (is_deleted=False) so onboarding and reuse are
    possible for the same id.
    """
    # Reuse erase_user_data to perform removes and anonymization first
    erase_user_data(session, user_id, reason, actor)

    # Re-activate the user row so the id can be reused
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise ValueError("User not found")
    user = cast(Any, user)

    # Restore active flags and clear deletion markers while keeping contact
    # information removed. Use a predictable external_id so the id can be
    # referenced from tests/UI.
    user.is_deleted = False
    user.deleted_at = None
    user.processing_restricted = False
    user.opted_in = False
    user.restriction_reason = None
    user.external_id = f"cleaned-{user_id}"
    user.channel = "web"

    session.add(user)
    session.commit()

    record_gdpr_request(
        session=session,
        user_id=user_id,
        request_type="clean",
        status="completed",
        actor=actor,
        reason=reason,
    )
    record_gdpr_audit(
        session=session,
        user_id=user_id,
        action="clean",
        actor=actor,
        details={"reason": reason},
    )
