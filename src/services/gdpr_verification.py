from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.models.database import GdprVerification


from src.core.timezone import to_utc, utc_now as _utc_now


def _ensure_utc_aware(dt: datetime) -> datetime:
    return to_utc(dt)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_verification(
    session: Session,
    user_id: int,
    channel: str,
    request_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    code = _generate_code(settings.GDPR_VERIFICATION_CODE_LENGTH)
    expires_at = _utc_now() + timedelta(minutes=settings.GDPR_VERIFICATION_TTL_MINUTES)
    verification = GdprVerification(
        user_id=user_id,
        channel=channel,
        request_type=request_type,
        request_payload=json.dumps(payload or {}),
        code_hash=_hash_code(code),
        attempts=0,
        expires_at=expires_at,
        created_at=_utc_now(),
    )
    session.add(verification)
    session.commit()
    return code


def verify_code(
    session: Session,
    user_id: int,
    code: str,
) -> GdprVerification:
    verification = (
        session.query(GdprVerification)
        .filter(
            GdprVerification.user_id == user_id,
            GdprVerification.verified_at == None,
        )
        .order_by(GdprVerification.created_at.desc())
        .first()
    )
    if not verification:
        raise ValueError("No pending verification")

    if _ensure_utc_aware(verification.expires_at) < _utc_now():
        raise ValueError("Verification expired")

    if verification.attempts >= settings.GDPR_VERIFICATION_MAX_ATTEMPTS:
        raise ValueError("Too many attempts")

    if verification.code_hash != _hash_code(code):
        verification.attempts += 1
        session.add(verification)
        session.commit()
        raise ValueError("Invalid code")

    verification.verified_at = _utc_now()
    session.add(verification)
    session.commit()
    return verification


def _generate_code(length: int) -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))
