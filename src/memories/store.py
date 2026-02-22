"""Store abstraction for memory persistence backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from .types import MemoryEntity, MemoryRecord


class MemoryStore(ABC):
    """Abstract memory persistence API.

    Implement this to swap SQL-backed storage with another backend.
    """

    @abstractmethod
    def get_memory(self, user_id: int, key: str) -> List[MemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def store_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "dialogue_engine",
        ttl_hours: Optional[int] = None,
        category: str = "fact",
        allow_duplicates: bool = False,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def archive_memories(self, user_id: int, memory_ids: List[int]) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_active_memories(
        self,
        user_id: int,
        categories: Optional[List[str]] = None,
        order_ascending: bool = False,
    ) -> List[MemoryEntity]:
        raise NotImplementedError

    @abstractmethod
    def keyword_candidates(
        self,
        user_id: int,
        query_text: str,
        categories: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[MemoryEntity]:
        raise NotImplementedError

    @abstractmethod
    def top_active_memories(
        self,
        user_id: int,
        categories: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[MemoryEntity]:
        raise NotImplementedError

    @abstractmethod
    def list_user_memories(self, user_id: int) -> List[MemoryEntity]:
        raise NotImplementedError

    @abstractmethod
    def get_user_memory_by_id(self, user_id: int, memory_id: int) -> Optional[MemoryEntity]:
        raise NotImplementedError

    @abstractmethod
    def delete_user_memories(self, user_id: int, commit: bool = False) -> int:
        raise NotImplementedError

    @abstractmethod
    def delete_all_memories(self, commit: bool = False) -> int:
        raise NotImplementedError

    @abstractmethod
    def purge_archived_before(self, cutoff: datetime) -> int:
        raise NotImplementedError

    @abstractmethod
    def purge_expired_ttl_before(self, cutoff: datetime) -> int:
        raise NotImplementedError
