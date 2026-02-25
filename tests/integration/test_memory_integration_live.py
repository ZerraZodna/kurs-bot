"""
Migrated live integration tests for memory with real Ollama.
 migrated from tests/test_memory_integration_live.py
"""
import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, User, Memory
from src.services.dialogue_engine import DialogueEngine
from src.config import settings
from tests.utils import make_ready_user


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Add a user for FK
    user = User(external_id="99997", channel="telegram", first_name="Live", last_name="User", opted_in=True)
    session.add(user)
    session.commit()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_birthdate_memory_stored_with_real_ollama(db_session):
    """Given: A user sends a message containing their birthdate
    When: The dialogue engine processes the message through the full production path with real Ollama
    Then: A memory containing the birthdate is stored
    """
    # Quick health check to see if Ollama is reachable. Skip test if it's not.
    ollama_url = getattr(settings, "LOCAL_OLLAMA_URL", "http://localhost:11434/api/generate")
    try:
        # Try GET first (some Ollama deployments respond to GET for health)
        resp = httpx.get(ollama_url, timeout=5.0)
        if resp.status_code == 200:
            pass
        elif resp.status_code == 405:
            # Method not allowed — check Allow header for POST support
            allow = resp.headers.get("allow", "")
            if "POST" in allow.upper():
                pass
            else:
                # Try OPTIONS to inspect allowed methods
                try:
                    resp2 = httpx.options(ollama_url, timeout=5.0)
                    allow2 = resp2.headers.get("allow", "")
                    if "POST" in allow2.upper() or resp2.status_code == 200:
                        pass
                    else:
                        pytest.skip("Ollama endpoint does not allow POST; skipping live integration test")
                except Exception:
                    pytest.skip("Ollama returned 405 and OPTIONS failed; skipping live integration test")
        else:
            # Fallback: try a lightweight POST to verify the generate endpoint
            resp3 = httpx.post(
                ollama_url,
                json={"model": getattr(settings, "OLLAMA_MODEL", None), "prompt": "ping", "stream": False},
                timeout=5.0,
            )
            if resp3.status_code >= 400:
                pytest.skip("Ollama returned non-2xx status; skipping live integration test")
    except Exception:
        pytest.skip("Ollama not available; skipping live integration test")

    # Given: Create engine and dialogue engine bound to our test session
    engine = DialogueEngine(db=db_session)

    # Ensure user has completed onboarding so extraction runs (avoid name prompt)
    make_ready_user(db_session, "99997")
    user = db_session.query(User).filter_by(external_id="99997").first()

    # When: Send the message via the full production code path
    await engine.process_message(user.user_id, "I am born 23.05.1966", session=db_session)

    # Then: Query Memories table for any value containing a 4-digit year (e.g., 1966)
    import re

    all_mems = db_session.query(Memory).filter(Memory.user_id == user.user_id).all()
    values = [str(m.value or "") for m in all_mems]
    year_re = re.compile(r"\b(19|20)\d{2}\b")
    matched = [v for v in values if year_re.search(v)]

    assert matched, f"No memory with a year-like value was stored; stored values: {values}"

