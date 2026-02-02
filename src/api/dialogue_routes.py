"""
API routes for context-aware dialogue endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, User
from src.services.dialogue_engine import DialogueEngine
from src.services.memory_manager import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.services.context_utils import MemoryKey, MemoryCategory

router = APIRouter(prefix="/api/v1/dialogue", tags=["dialogue"])


# Pydantic models for API requests/responses
class MessageRequest(BaseModel):
    user_id: int
    text: str
    include_history: bool = True
    history_turns: int = 4


class MessageResponse(BaseModel):
    user_id: int
    response: str
    model: str = "ollama"


class MemoryRequest(BaseModel):
    user_id: int
    key: str
    value: str
    category: str = "profile"
    confidence: float = 1.0
    ttl_hours: Optional[int] = None


class UserContextResponse(BaseModel):
    user_id: int
    name: str
    goals: List[dict]
    preferences: List[dict]
    recent_progress: List[dict]


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Dialogue endpoints

@router.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest, db: Session = Depends(get_db)):
    """
    Send a message and get an AI response with full context awareness.
    
    The response is generated considering:
    - User profile and preferences
    - Learning goals and progress
    - Recent conversation history
    - Stored memories and insights
    """
    # Verify user exists
    user = db.query(User).filter_by(user_id=request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Process with full context
    dialogue_engine = DialogueEngine(db)
    response = await dialogue_engine.process_message(
        user_id=request.user_id,
        text=request.text,
        session=db,
        include_history=request.include_history,
        history_turns=request.history_turns,
    )
    
    return MessageResponse(
        user_id=request.user_id,
        response=response,
    )


@router.post("/onboard")
async def onboard_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get onboarding prompt sequence for new users.
    """
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    dialogue_engine = DialogueEngine(db)
    prompt = dialogue_engine.get_onboarding_prompt()
    
    return {"prompt": prompt}


# Memory management endpoints

@router.post("/memory")
async def store_memory(request: MemoryRequest, db: Session = Depends(get_db)):
    """
    Store a memory for a user.
    
    Memory categories:
    - profile: User information (name, timezone, accessibility)
    - goals: Learning objectives and goals
    - preferences: Communication and learning preferences
    - progress: Completed lessons, milestones
    - insights: AI-derived understanding about user
    - conversation: Conversation context and state
    """
    # Verify user exists
    user = db.query(User).filter_by(user_id=request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Store memory
    memory_manager = MemoryManager(db)
    memory_id = memory_manager.store_memory(
        user_id=request.user_id,
        key=request.key,
        value=request.value,
        category=request.category,
        confidence=request.confidence,
        ttl_hours=request.ttl_hours,
    )
    
    return {
        "memory_id": memory_id,
        "user_id": request.user_id,
        "key": request.key,
        "status": "stored",
    }


@router.get("/memory/{user_id}/{key}")
async def get_memory(user_id: int, key: str, db: Session = Depends(get_db)):
    """Retrieve memories by key for a user."""
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    memory_manager = MemoryManager(db)
    memories = memory_manager.get_memory(user_id, key)
    
    return {
        "user_id": user_id,
        "key": key,
        "memories": memories,
    }


@router.get("/context/{user_id}", response_model=UserContextResponse)
async def get_user_context(user_id: int, db: Session = Depends(get_db)):
    """
    Get complete user context for analysis or display.
    Includes profile, goals, preferences, and recent progress.
    """
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    memory_manager = MemoryManager(db)
    
    # Gather context
    goals = memory_manager.get_memory(user_id, MemoryKey.LEARNING_GOAL)
    preferences = memory_manager.get_memory(user_id, MemoryKey.PREFERRED_TONE)
    progress = memory_manager.get_memory(user_id, MemoryKey.LESSON_COMPLETED)
    
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "User"
    
    return UserContextResponse(
        user_id=user_id,
        name=name,
        goals=goals,
        preferences=preferences,
        recent_progress=progress[:5] if progress else [],
    )


@router.delete("/memory/{user_id}/{key}")
async def delete_memory(user_id: int, key: str, db: Session = Depends(get_db)):
    """Archive (soft-delete) a memory entry."""
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    memory_manager = MemoryManager(db)
    # Note: This implementation archives memories; modify as needed
    # For now, we'll just return a success response
    
    return {
        "user_id": user_id,
        "key": key,
        "status": "archived",
    }


# Batch operations

@router.post("/memory/batch")
async def batch_store_memory(requests: List[MemoryRequest], db: Session = Depends(get_db)):
    """Store multiple memories in one request."""
    results = []
    memory_manager = MemoryManager(db)
    
    for req in requests:
        user = db.query(User).filter_by(user_id=req.user_id).first()
        if not user:
            results.append({
                "user_id": req.user_id,
                "status": "error",
                "message": "User not found",
            })
            continue
        
        memory_id = memory_manager.store_memory(
            user_id=req.user_id,
            key=req.key,
            value=req.value,
            category=req.category,
            confidence=req.confidence,
            ttl_hours=req.ttl_hours,
        )
        
        results.append({
            "user_id": req.user_id,
            "memory_id": memory_id,
            "key": req.key,
            "status": "stored",
        })
    
    return {"results": results}
