from typing import List

from pydantic import BaseModel

# Dialogue endpoints


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
    ttl_hours: int | None = None


class UserContextResponse(BaseModel):
    user_id: int
    name: str
    goals: List[dict]
    preferences: List[dict]
    recent_progress: List[dict]


class LessonResponse(BaseModel):
    lesson_id: int
    title: str
    content: str
    difficulty_level: str
    duration_minutes: int


class SemanticSearchRequest(BaseModel):
    user_id: int
    query: str
    categories: List[str] | None = None
    limit: int | None = None
    threshold: float | None = None


class MemoryWithScore(BaseModel):
    memory_id: int
    key: str
    value: str
    category: str
    similarity_score: float


class SemanticSearchResponse(BaseModel):
    user_id: int
    query: str
    results: List[MemoryWithScore]
    count: int
