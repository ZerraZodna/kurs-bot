from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import settings
from src.models.database import SessionLocal, User
from src.services.gdpr_service import (
    erase_user_data,
    export_user_data,
    object_to_processing,
    rectify_user,
    restrict_processing,
    withdraw_consent,
)

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


def require_gdpr_admin(
    x_gdpr_token: str | None = Header(default=None, alias="X-GDPR-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    expected = settings.GDPR_ADMIN_TOKEN
    if not expected:
        raise HTTPException(status_code=503, detail="GDPR admin token not configured")

    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_gdpr_token:
        token = x_gdpr_token.strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing GDPR admin token")
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid GDPR admin token")


class GdprExportRequest(BaseModel):
    user_id: int


class GdprRestrictRequest(BaseModel):
    user_id: int
    reason: str | None = None
    actor: str = "user"


class MemoryRectifyItem(BaseModel):
    memory_id: int
    value: str


class GdprRectifyRequest(BaseModel):
    user_id: int
    updates: Dict[str, Any] = {}
    memory_updates: List[MemoryRectifyItem] | None = None
    actor: str = "user"


class GdprEraseRequest(BaseModel):
    user_id: int
    reason: str | None = None
    actor: str = "user"


class GdprCleanRequest(BaseModel):
    user_id: int
    reason: str | None = None
    actor: str = "user"


class GdprObjectRequest(BaseModel):
    user_id: int
    reason: str | None = None
    actor: str = "user"


class GdprWithdrawConsentRequest(BaseModel):
    user_id: int
    scope: str = "data_storage"
    reason: str | None = None
    actor: str = "user"


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/export")
async def gdpr_export(
    request: GdprExportRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    user = db.query(User).filter_by(user_id=request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        data = export_user_data(db, request.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return data


@router.get("/export/{user_id}")
async def gdpr_export_get(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        data = export_user_data(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return data


@router.post("/restrict")
async def gdpr_restrict(
    request: GdprRestrictRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    try:
        restrict_processing(db, request.user_id, request.reason, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "restricted", "user_id": request.user_id}


@router.post("/object")
async def gdpr_object(
    request: GdprObjectRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    try:
        object_to_processing(db, request.user_id, request.reason, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "objected", "user_id": request.user_id}


@router.post("/rectify")
async def gdpr_rectify(
    request: GdprRectifyRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    try:
        memory_updates = [item.model_dump() for item in request.memory_updates] if request.memory_updates else None
        rectify_user(db, request.user_id, request.updates, memory_updates, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "rectified", "user_id": request.user_id}


@router.post("/erase")
async def gdpr_erase(
    request: GdprEraseRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    try:
        erase_user_data(db, request.user_id, request.reason, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "erased", "user_id": request.user_id}


@router.post("/clean")
async def gdpr_clean(
    request: GdprCleanRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    try:
        from src.services.gdpr_service import clean_user_data

        clean_user_data(db, request.user_id, request.reason, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "cleaned", "user_id": request.user_id}


@router.post("/withdraw-consent")
async def gdpr_withdraw_consent(
    request: GdprWithdrawConsentRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_gdpr_admin),
) -> Dict[str, Any]:
    try:
        withdraw_consent(db, request.user_id, request.scope, request.actor, request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "withdrawn", "user_id": request.user_id}


@router.get("/privacy-notice")
async def gdpr_privacy_notice() -> Dict[str, Any]:
    notice_path = Path(__file__).resolve().parents[2] / "docs" / "gdpr" / "PRIVACY_NOTICE.md"
    if notice_path.exists():
        return {"content": notice_path.read_text(encoding="utf-8")}
    return {"content": "Privacy notice not configured yet."}
