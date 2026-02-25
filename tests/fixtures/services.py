"""Service fixtures for tests."""

import datetime
from typing import Generator, Optional
from unittest.mock import MagicMock, AsyncMock

import pytest
from sqlalchemy.orm import Session

from src.memories import MemoryManager
from src.services.dialogue_engine import DialogueEngine
from src.scheduler import SchedulerService
from src.services.embedding_service import EmbeddingService
from src.models.database import Lesson


@pytest.fixture
def lesson(db_session: Session) -> Lesson:
    """A basic lesson for testing."""
    lesson = Lesson(
        title="Test Lesson",
        content="This is test content for lesson 1.",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(lesson)
    db_session.commit()
    return lesson


@pytest.fixture
def memory_manager(db_session: Session) -> MemoryManager:
    """MemoryManager instance bound to test database."""
    return MemoryManager(db=db_session)


@pytest.fixture
def dialogue_engine(db_session: Session) -> DialogueEngine:
    """DialogueEngine instance bound to test database."""
    return DialogueEngine(db_session)


@pytest.fixture
def scheduler_service() -> Generator[SchedulerService, None, None]:
    """SchedulerService fixture with automatic cleanup.
    
    Initializes the scheduler before test and shuts down after.
    """
    SchedulerService.init_scheduler()
    yield SchedulerService
    SchedulerService.shutdown()


@pytest.fixture
def mock_embedding_service(monkeypatch) -> MagicMock:
    """Mocked EmbeddingService that returns zero vectors.
    
    Use this to avoid heavy ML dependencies in tests.
    """
    mock_service = MagicMock(spec=EmbeddingService)
    mock_service.embedding_dimension = 384
    
    # Mock async methods
    async def mock_generate_embedding(text: str) -> Optional[list]:
        if not text:
            return None
        return [0.0] * mock_service.embedding_dimension
    
    async def mock_batch_embed(texts: list) -> list:
        return [
            None if not t else [0.0] * mock_service.embedding_dimension
            for t in texts
        ]
    
    async def mock_close() -> None:
        pass
    
    mock_service.generate_embedding = AsyncMock(side_effect=mock_generate_embedding)
    mock_service.batch_embed = AsyncMock(side_effect=mock_batch_embed)
    mock_service.close = AsyncMock(side_effect=mock_close)
    
    # Patch the module
    import src.services.embedding_service as emb_module
    monkeypatch.setattr(emb_module, "get_embedding_service", lambda: mock_service)
    monkeypatch.setattr(emb_module, "_embedding_service", mock_service)
    
    return mock_service


@pytest.fixture
def mock_ollama_client(monkeypatch) -> MagicMock:
    """Mocked Ollama client for dialogue tests.
    
    Returns predictable responses without making real HTTP calls.
    """
    mock_client = MagicMock()
    
    async def mock_call_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None) -> str:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"
    
    mock_client.call_ollama = AsyncMock(side_effect=mock_call_ollama)
    
    # Patch the module
    import src.services.dialogue.ollama_client as ollama_module
    monkeypatch.setattr(ollama_module, "call_ollama", mock_call_ollama)
    
    return mock_client


@pytest.fixture
def frozen_time() -> datetime.datetime:
    """Frozen datetime for deterministic time-based tests.
    
    Returns a fixed UTC datetime that can be used for consistent
    time-based assertions.
    """
    return datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
