from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.database import SessionLocal, User
from src.services.gdpr_service import (
    export_user_data,
    restrict_processing,
    rectify_user,
    erase_user_data,
)

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


class GdprExportRequest(BaseModel):
    user_id: int


class GdprRestrictRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None
    actor: str = "user"


class MemoryRectifyItem(BaseModel):
    memory_id: int
    value: str


class GdprRectifyRequest(BaseModel):
    user_id: int
    updates: Dict[str, Any] = {}
    memory_updates: Optional[List[MemoryRectifyItem]] = None
    actor: str = "user"


class GdprEraseRequest(BaseModel):
    user_id: int
    reason: Optional[str] = None
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
async def gdpr_export(request: GdprExportRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = db.query(User).filter_by(user_id=request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        data = export_user_data(db, request.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return data


@router.get("/export/{user_id}")
async def gdpr_export_get(user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        data = export_user_data(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return data


@router.post("/restrict")
async def gdpr_restrict(request: GdprRestrictRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        restrict_processing(db, request.user_id, request.reason, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"status": "restricted", "user_id": request.user_id}


@router.post("/rectify")
async def gdpr_rectify(request: GdprRectifyRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        memory_updates = (
            [item.model_dump() for item in request.memory_updates]
            if request.memory_updates
            else None
        )
        rectify_user(db, request.user_id, request.updates, memory_updates, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"status": "rectified", "user_id": request.user_id}


@router.post("/erase")
async def gdpr_erase(request: GdprEraseRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        erase_user_data(db, request.user_id, request.reason, request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"status": "erased", "user_id": request.user_id}


@router.get("/privacy-notice")
async def gdpr_privacy_notice() -> Dict[str, Any]:
    notice_path = Path(__file__).resolve().parents[2] / "docs" / "PRIVACY_NOTICE.md"
    if notice_path.exists():
        return {"content": notice_path.read_text(encoding="utf-8")}
    return {"content": "Privacy notice not configured yet."}
