import asyncio
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from src.models.database import Base, User, Memory
from src.services.memory_manager import MemoryManager
from src.services.dialogue.command_handlers import handle_rag_mode_toggle


class DummyEmbedSvc:
    def __init__(self, dim=4):
        self.dim = dim

    async def generate_embedding(self, text: str):
        # return a deterministic small embedding
        return [1.0] * self.dim

    def embedding_to_bytes(self, emb):
        import numpy as np

        return np.array(emb, dtype="float32").tobytes()

    def bytes_to_embedding(self, data):
        import numpy as np

        return np.frombuffer(data, dtype="float32").tolist()


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Ensure module-level SessionLocal used elsewhere points to our test sessionmaker
    import src.models.database as _dbmod
    _orig_session_local = getattr(_dbmod, "SessionLocal", None)
    _dbmod.SessionLocal = Session
    # Also ensure MemoryManager module uses the same SessionLocal reference
    import src.services.memory_manager as _mmod
    _orig_mm_session_local = getattr(_mmod, "SessionLocal", None)
    try:
        _mmod.SessionLocal = Session
    except Exception:
        # older import style in module may not expose SessionLocal; ignore
        _orig_mm_session_local = None
    # create a user for FK
    user = User(external_id="u1", channel="test", first_name="T", last_name="U", opted_in=True, created_at=datetime.datetime.utcnow())
    session.add(user)
    session.commit()
    yield session
    session.close()
    # restore original SessionLocal
    try:
        _dbmod.SessionLocal = _orig_session_local
    except Exception:
        pass
    try:
        if _orig_mm_session_local is not None:
            _mmod.SessionLocal = _orig_mm_session_local
    except Exception:
        pass


def test_rag_mode_on_generates_embedding(monkeypatch, db_session):
    # Point embedding service to dummy (patch both modules that reference it)
    monkeypatch.setattr("src.services.embedding_service.get_embedding_service", lambda: DummyEmbedSvc())
    monkeypatch.setattr("src.services.memory_manager.get_embedding_service", lambda: DummyEmbedSvc())

    user = db_session.query(User).first()
    mm = MemoryManager(db=db_session)

    # Ensure no prior rag memory
    assert db_session.query(Memory).filter_by(user_id=user.user_id, key="rag_mode_enabled").count() == 0

    # Test multiple command variants that should enable RAG mode
    variants = ["rag_mode on", "rag mode on", "rag on", "rag: on"]
    for v in variants:
        # ensure clean state
        db_session.query(Memory).filter_by(user_id=user.user_id, key="rag_mode_enabled").delete()
        db_session.commit()

        resp = handle_rag_mode_toggle(v, mm, user.user_id)
        assert resp and "enabled" in resp.lower(), f"Unexpected response for '{v}': {resp}"

        # Query memory row and assert embedding fields populated
        mem = db_session.query(Memory).filter_by(user_id=user.user_id, key="rag_mode_enabled", is_active=True).first()
        assert mem is not None, f"Memory row for rag_mode_enabled not found after '{v}'"
        assert mem.embedding is not None and len(mem.embedding) > 0, f"Embedding was not generated for '{v}'"
        assert mem.embedding_version is not None
        assert mem.embedding_generated_at is not None
