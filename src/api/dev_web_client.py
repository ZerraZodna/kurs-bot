from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from src.models.database import SessionLocal, User
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.config import settings

router = APIRouter(prefix="/dev")


class MessagePayload(BaseModel):
    user_id: int
    text: str


@router.post("/message")
async def dev_message(payload: MessagePayload):
    # Create or ensure a user exists for the given user_id
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=payload.user_id).first()
        if not user:
            # Create lightweight user record for dev channel
            user = User(external_id=str(payload.user_id), channel="web", first_name="Dev", opted_in=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        # Use DialogueEngine to process message
        dialogue = DialogueEngine(db)
        response = await dialogue.process_message(user_id=user.user_id, text=payload.text, session=db)
        return {"ok": True, "response": response}
    finally:
        db.close()


@router.get("/ui")
async def dev_ui():
    # Simple redirect/placeholder — static files are mounted at /dev/static
    return {"ok": True, "ui": "/dev/static/index.html"}
