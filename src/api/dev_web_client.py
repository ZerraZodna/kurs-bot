from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import socket
import getpass

from src.models.database import SessionLocal, User
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.config import settings
import logging
from fastapi.responses import StreamingResponse
from src.integrations.telegram_stream import StreamingFilter

router = APIRouter(prefix="/dev")


class MessagePayload(BaseModel):
    # Keep `user_id` optional for compatibility but it will be ignored by the server.
    user_id: Optional[int] = None
    text: str


def _get_server_user_identifier() -> str:
    """Return a stable identifier derived from the server OS environment.

    Uses username@hostname (Windows: USERNAME/COMPUTERNAME; *nix: USER/HOSTNAME).
    This ensures the dev web UI cannot impersonate other users by sending user_id.
    """
    user = os.environ.get("USERNAME") or os.environ.get("USER") or getpass.getuser()
    host = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or socket.gethostname()
    return f"{user}@{host}"


@router.post("/message")
async def dev_message(payload: MessagePayload):
    # Ignore any client-supplied user_id and derive a server-side identifier
    server_identifier = _get_server_user_identifier()

    db = SessionLocal()
    try:
        # Find a lightweight user record tied to this server/process
        user = db.query(User).filter_by(external_id=str(server_identifier), channel="web").first()
        if not user:
            # Create lightweight user record for dev channel using server identifier
            user = User(external_id=str(server_identifier), channel="web", first_name="Dev", opted_in=True)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Use DialogueEngine to process message
        dialogue = DialogueEngine(db)
        response = await dialogue.process_message(user_id=user.user_id, text=payload.text, session=db)
        
        logger = logging.getLogger(__name__)
        
        if isinstance(response, dict) and response.get("type") == "stream":
            raw_generator = response["generator"]
            stream_filter = StreamingFilter(raw_generator)
            filtered_generator = stream_filter.filter_stream()
            
            async def webui_stream_gen():
                async for token in filtered_generator:
                    yield token
                # Run post-hook (full_text accumulation needs tee in prod)
                try:
                    await response["post_hook"]("")
                except Exception as e:
                    logger.error(f"Post-hook error: {e}")
            
            return StreamingResponse(webui_stream_gen(), media_type="text/plain")
        else:
            # Fallback to text if not stream dict
            return {"ok": True, "response": response.get("text", str(response))}
    finally:
        db.close()


@router.get("/ui")
async def dev_ui():
    # Simple redirect/placeholder — static files are mounted at /dev/static
    return {"ok": True, "ui": "/dev/static/index.html"}
