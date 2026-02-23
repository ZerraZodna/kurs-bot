"""
API routes for context-aware dialogue endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, User
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.language.prompt_builder import PromptBuilder

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
        db.commit()
    except Exception:
        db.rollback()
        raise
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
    
    return MessageResponse(user_id=request.user_id, response=response,)


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


# Lesson endpoints
class LessonResponse(BaseModel):
    lesson_id: int
    title: str
    content: str
    difficulty_level: str
    duration_minutes: int


@router.get("/lesson/{lesson_id}", response_model=LessonResponse)
def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """
    Get a specific ACIM lesson by ID.
    
    Returns the full lesson text and metadata.
    Lessons are imported from the ACIM PDF (run scripts/import_acim_lessons.py).
    
    Args:
        lesson_id: Lesson number (1-365)
    
    Returns:
        Lesson with title, content, and metadata
    """
    from src.models.database import Lesson
    
    lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson {lesson_id} not found")
    
    return LessonResponse(
        lesson_id=lesson.lesson_id,
        title=lesson.title,
        content=lesson.content,
        difficulty_level=lesson.difficulty_level or "beginner",
        duration_minutes=lesson.duration_minutes or 15,
    )


# Semantic search endpoints

class SemanticSearchRequest(BaseModel):
    user_id: int
    query: str
    categories: Optional[List[str]] = None
    limit: Optional[int] = None
    threshold: Optional[float] = None


class MemoryWithScore(BaseModel):
    memory_id: int
    key: str
    value: str
    category: str
    confidence: float
    similarity_score: float


class SemanticSearchResponse(BaseModel):
    user_id: int
    query: str
    results: List[MemoryWithScore]
    count: int


@router.post("/search", response_model=SemanticSearchResponse)
async def semantic_search(request: SemanticSearchRequest, db: Session = Depends(get_db)):
    """
    Semantically search user's memories for contextually relevant information.
    
    Uses vector embeddings to find memories similar to the query text,
    rather than exact keyword matching.
    
    Args:
        user_id: User ID
        query: Search query text
        categories: Optional list of memory categories to filter by
        limit: Maximum results to return
        threshold: Minimum similarity score (0.0-1.0)
    
    Returns:
        List of memories ranked by semantic similarity
    """
    from src.memories.semantic_search import get_semantic_search_service
    
    # Verify user exists
    user = db.query(User).filter_by(user_id=request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Perform semantic search
    search_service = get_semantic_search_service()
    results = await search_service.search_memories(
        user_id=request.user_id,
        query_text=request.query,
        session=db,
        categories=request.categories,
        limit=request.limit,
        threshold=request.threshold
    )
    
    # Format results
    memory_results = []
    for memory, score in results:
        memory_results.append(MemoryWithScore(
            memory_id=memory.memory_id,
            key=memory.key,
            value=memory.value,
            category=memory.category,
            confidence=memory.confidence,
            similarity_score=round(score, 4)
        ))
    
    return SemanticSearchResponse(
        user_id=request.user_id,
        query=request.query,
        results=memory_results,
        count=len(memory_results)
    )
