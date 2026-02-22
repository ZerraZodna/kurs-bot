"""Typed records and protocols for memory domain objects."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, TypedDict, runtime_checkable


class MemoryRecord(TypedDict):
    """Public memory payload returned by memory reads."""

    memory_id: int
    key: str
    value: str
    confidence: float
    source: str
    created_at: datetime


@runtime_checkable
class MemoryEntity(Protocol):
    """Protocol for memory-like ORM/domain objects used by search/ranking."""

    memory_id: int
    user_id: int
    key: str
    value: str
    category: str
    confidence: float
    is_active: bool
    source: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    archived_at: Optional[datetime]
    ttl_expires_at: Optional[datetime]
    embedding: Optional[bytes]
