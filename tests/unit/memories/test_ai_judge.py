"""
Unit tests for AI Memory Judge.

These tests verify that the MemoryJudge correctly:
1. Cleans corrupted values (e.g., "spelled backwards sennahoJ" → "Johannes")
2. Scores memory quality (0.0-1.0)
3. Detects conflicts with existing memories
4. Respects conftest.py model configuration (TEST_OLLAMA_* env vars)
"""

import pytest
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.memories.ai_judge import MemoryJudge, StorageDecision


@dataclass
class MockMemory:
    """Mock memory for testing."""
    memory_id: int
    key: str
    value: str
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            # Use recent date so AI doesn't consider memory "outdated"
            self.created_at = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def judge():
    """Create a MemoryJudge instance for testing."""
    return MemoryJudge()


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
async def test_clean_corrupted_name_backwards_spelling(judge):
    """
    Test that the AI judge detects and handles corrupted name values.
    
    Example from prod.db: "No, my full name is spelled backwards sennahoJ"
    AI should either clean it to "Johannes" or flag it as corrupted.
    """
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="first_name",
        proposed_value="No, my full name is spelled backwards sennahoJ",
        user_message="No, my full name is spelled backwards sennahoJ",
        existing_memories=[]
    )
    
    # AI should either clean the value OR flag it as low quality/corrupted
    # Different models may handle this differently
    is_cleaned = decision.cleaned_value == "Johannes"
    is_flagged = decision.quality_score < 0.7 or not decision.should_store or len(decision.issues) > 0
    
    assert is_cleaned or is_flagged, f"AI should clean 'sennahoJ' to 'Johannes' or flag as corrupted. Got cleaned_value='{decision.cleaned_value}', quality={decision.quality_score}, should_store={decision.should_store}, issues={decision.issues}"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
async def test_valid_name_high_quality(judge):
    """Test that valid names get high quality scores."""
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="first_name",
        proposed_value="Johannes",
        user_message="My name is Johannes",
        existing_memories=[]
    )
    
    assert decision.quality_score >= 0.9, f"Valid name should have high quality, got {decision.quality_score}"
    assert decision.should_store is True
    assert decision.cleaned_value == "Johannes"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
async def test_duplicate_detection(judge):
    """Test that duplicates are detected or flagged as high quality."""
    existing = [MockMemory(1, "first_name", "Johannes")]
    
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="first_name",
        proposed_value="Johannes",
        user_message="My name is Johannes",
        existing_memories=existing
    )
    
    # AI should either detect the duplicate OR mark it as high quality valid data
    # Different models handle this differently - some detect conflicts, others just validate
    has_conflict = len(decision.conflicts) > 0
    is_valid_duplicate = decision.quality_score >= 0.9 and decision.should_store and decision.cleaned_value == "Johannes"
    
    assert has_conflict or is_valid_duplicate, f"Should either detect duplicate conflict or validate as high-quality. Got conflicts={decision.conflicts}, quality={decision.quality_score}, should_store={decision.should_store}"
    
    # If conflict detected, verify it references the existing memory
    if has_conflict:
        assert any(c.existing_memory_id == 1 for c in decision.conflicts), "Should reference existing memory"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
async def test_name_update_detection(judge):
    """Test that name updates are handled correctly."""
    existing = [MockMemory(1, "first_name", "Bob")]
    
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="first_name",
        proposed_value="Robert",
        user_message="Actually, my name is Robert, not Bob",
        existing_memories=existing
    )
    
    # Should detect conflict and suggest REPLACE
    assert len(decision.conflicts) > 0, "Should detect conflict with old name"
    conflict = decision.conflicts[0]
    assert conflict.action in ["REPLACE", "FLAG"], f"Should suggest REPLACE or FLAG, got {conflict.action}"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
async def test_low_quality_rejection(judge):
    """Test that low-quality memories are flagged."""
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="user_fact",
        proposed_value="uhh maybe like 5 or something?",
        user_message="uhh maybe like 5 or something?",
        existing_memories=[]
    )
    
    # Vague uncertain statements should get lower quality
    assert decision.quality_score < 0.7, f"Uncertain statement should have low quality, got {decision.quality_score}"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
async def test_caching(judge):
    """Test that decisions are cached."""
    # First call
    decision1 = await judge.evaluate_storage(
        user_id=1,
        proposed_key="test",
        proposed_value="value",
        user_message="test message",
        existing_memories=[]
    )
    
    # Second call with same parameters should use cache
    decision2 = await judge.evaluate_storage(
        user_id=1,
        proposed_key="test",
        proposed_value="value",
        user_message="test message",
        existing_memories=[]
    )
    
    # Should be same object from cache
    assert decision1 is decision2, "Should return cached decision"


def test_storage_decision_parse():
    """Test parsing of StorageDecision from JSON."""
    data = {
        "should_store": True,
        "quality_score": 0.85,
        "issues": [],
        "cleaned_value": "Johannes",
        "conflicts": [
            {
                "existing_memory_id": 1,
                "reason": "Same person, different spelling",
                "action": "REPLACE",
                "existing_value": "sennahoJ"
            }
        ],
        "reasoning": "Cleaned backwards spelling"
    }
    
    decision = StorageDecision.parse(data)
    
    assert decision.should_store is True
    assert decision.quality_score == 0.85
    assert decision.cleaned_value == "Johannes"
    assert len(decision.conflicts) == 1
    assert decision.conflicts[0].action == "REPLACE"


@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
def test_model_configuration_from_env():
    """
    Verify that conftest.py properly configures test models.
    
    This test documents the expected behavior - conftest.py should:
    1. Load .env file
    2. Set TEST_OLLAMA_MODEL overrides
    3. Reload src.config so settings picks them up
    """
    # These should be set by conftest.py if TEST_OLLAMA_MODEL is in env
    ollama_model = os.environ.get("OLLAMA_MODEL", "")
    ollama_chat_rag = os.environ.get("OLLAMA_CHAT_RAG_MODEL", "")
    
    # If TEST_* vars were set, they should be reflected in OLLAMA_* vars
    test_model = os.environ.get("TEST_OLLAMA_MODEL")
    test_chat_rag = os.environ.get("TEST_OLLAMA_CHAT_RAG_MODEL")
    
    if test_model:
        assert ollama_model == test_model, f"OLLAMA_MODEL should be {test_model}, got {ollama_model}"
    if test_chat_rag:
        assert ollama_chat_rag == test_chat_rag, f"OLLAMA_CHAT_RAG_MODEL should be {test_chat_rag}, got {ollama_chat_rag}"
