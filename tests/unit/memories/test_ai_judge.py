"""
Unit tests for AI Memory Judge.

These tests verify that the MemoryJudge correctly:
1. Cleans corrupted values (e.g., "spelled backwards sennahoJ" → "Johannes")
2. Scores memory quality (0.0-1.0)
3. Detects conflicts with existing memories
4. Uses helper methods that can be mocked for testing

The tests use mocking for Ollama calls to avoid requiring real AI responses.
"""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from src.memories.ai_judge import MemoryJudge
from src.memories.judge_core import parse_extraction_response, filter_valid_memories


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


class TestHelperMethods:
    """Test the helper methods in MemoryJudge."""
    
    def test_build_prompt(self, judge):
        """Test prompt building."""
        prompt = judge._build_prompt(
            user_message="My name is Johannes",
            context_str=""
        )
        assert "My name is Johannes" in prompt
        assert "memories" in prompt.lower()
    
    def test_build_prompt_with_context(self, judge):
        """Test prompt building with existing memories."""
        context = '[{"memory_id": 1, "key": "first_name", "value": "Bob"}]'
        prompt = judge._build_prompt(
            user_message="Actually my name is Robert",
            context_str=context
        )
        assert "Robert" in prompt
        assert "Bob" in prompt
    
    def test_parse_response_valid_json(self, judge):
        """Test response parsing with valid JSON."""
        response = '{"memories": [{"key": "first_name", "value": "Johannes", "should_store": true, "quality_score": 0.9}]}'
        memories = judge._parse_response(response)
        assert len(memories) == 1
        assert memories[0]["key"] == "first_name"
        assert memories[0]["value"] == "Johannes"
    
    def test_parse_response_markdown_json(self, judge):
        """Test response parsing with markdown code blocks."""
        response = '''```json
{"memories": [{"key": "first_name", "value": "Johannes", "should_store": true, "quality_score": 0.9}]}
```'''
        memories = judge._parse_response(response)
        assert len(memories) == 1
        assert memories[0]["key"] == "first_name"
    
    def test_filter_and_clean_memories_high_quality(self, judge):
        """Test filtering keeps high quality memories."""
        memories = [
            {"key": "first_name", "value": "Johannes", "should_store": True, "quality_score": 0.9},
            {"key": "last_name", "value": "Doe", "should_store": True, "quality_score": 0.5},  # Low quality
        ]
        filtered = judge._filter_and_clean_memories(memories, min_quality=0.7)
        assert len(filtered) == 1
        assert filtered[0]["key"] == "first_name"
    
    def test_filter_and_clean_memories_uses_cleaned_value(self, judge):
        """Test that cleaned_value is used when available."""
        memories = [
            {"key": "first_name", "value": "sennahoJ", "cleaned_value": "Johannes", 
             "should_store": True, "quality_score": 0.9},
        ]
        filtered = judge._filter_and_clean_memories(memories)
        assert filtered[0]["value"] == "Johannes"


class TestExtractAndJudgeMemories:
    """Test the extract_and_judge_memories method with mocked Ollama."""
    
    @pytest.mark.asyncio
    async def test_clean_corrupted_name_backwards_spelling(self, judge):
        """Test that corrupted name values are cleaned or flagged."""
        # Mock Ollama response
        mock_response = '''{"memories": [{"key": "first_name", "value": "sennahoJ", 
            "cleaned_value": "Johannes", "should_store": true, "quality_score": 0.95,
            "reasoning": "Cleaned backwards spelling"}]}'''
        
        with patch.object(judge, '_call_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = mock_response
            
            result = await judge.extract_and_judge_memories(
                user_message="No, my full name is spelled backwards sennahoJ",
                user_context={"user_id": 1},
                existing_memories=[]
            )
        
        assert len(result) == 1
        # The cleaned_value should be used
        assert result[0]["value"] == "Johannes"
    
    @pytest.mark.asyncio
    async def test_valid_name_high_quality(self, judge):
        """Test that valid names get high quality scores."""
        mock_response = '''{"memories": [{"key": "first_name", "value": "Johannes",
            "should_store": true, "quality_score": 0.9,
            "reasoning": "Valid name, high confidence"}]}'''
        
        with patch.object(judge, '_call_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = mock_response
            
            result = await judge.extract_and_judge_memories(
                user_message="My name is Johannes",
                user_context={"user_id": 1},
                existing_memories=[]
            )
        
        assert len(result) == 1
        assert result[0]["quality_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(self, judge):
        """Test that duplicates are detected or flagged."""
        existing = [MockMemory(1, "first_name", "Johannes")]
        
        mock_response = '''{"memories": [{"key": "first_name", "value": "Johannes",
            "should_store": false, "quality_score": 0.5,
            "conflicts": [{"existing_memory_id": 1, "reason": "Duplicate", "action": "KEEP_EXISTING"}],
            "reasoning": "Duplicate memory detected"}]}'''
        
        with patch.object(judge, '_call_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = mock_response
            
            result = await judge.extract_and_judge_memories(
                user_message="My name is Johannes",
                user_context={"user_id": 1},
                existing_memories=existing
            )
        
        # Either it's filtered out (should_store=false) or has conflict info
        if len(result) == 0:
            # Good - duplicate was filtered
            pass
        else:
            # Or it has conflict info
            assert len(result[0].get("conflicts", [])) > 0
    
    @pytest.mark.asyncio
    async def test_name_update_detection(self, judge):
        """Test that name updates are handled correctly."""
        existing = [MockMemory(1, "first_name", "Bob")]
        
        mock_response = '''{"memories": [{"key": "first_name", "value": "Robert",
            "should_store": true, "quality_score": 0.9,
            "conflicts": [{"existing_memory_id": 1, "reason": "Name update", "action": "REPLACE",
             "existing_value": "Bob"}],
            "reasoning": "Name update detected"}]}'''
        
        with patch.object(judge, '_call_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = mock_response
            
            result = await judge.extract_and_judge_memories(
                user_message="Actually, my name is Robert, not Bob",
                user_context={"user_id": 1},
                existing_memories=existing
            )
        
        # Should either be valid with conflict or filtered
        if len(result) > 0:
            assert len(result[0].get("conflicts", [])) > 0
            conflict = result[0]["conflicts"][0]
            assert conflict["action"] in ["REPLACE", "FLAG"]
    
    @pytest.mark.asyncio
    async def test_low_quality_rejection(self, judge):
        """Test that low-quality memories are filtered out."""
        mock_response = '''{"memories": [{"key": "user_fact", "value": "uhh maybe like 5 or something?",
            "should_store": false, "quality_score": 0.3,
            "reasoning": "Uncertain statement"}]}'''
        
        with patch.object(judge, '_call_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = mock_response
            
            result = await judge.extract_and_judge_memories(
                user_message="uhh maybe like 5 or something?",
                user_context={"user_id": 1},
                existing_memories=[]
            )
        
        # Low quality should be filtered out
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_short_message_returns_empty(self, judge):
        """Test that very short messages return empty list."""
        result = await judge.extract_and_judge_memories(
            user_message="Hi",
            user_context={"user_id": 1},
            existing_memories=[]
        )
        assert result == []
    
    @pytest.mark.asyncio
    async def test_empty_message_returns_empty(self, judge):
        """Test that empty messages return empty list."""
        result = await judge.extract_and_judge_memories(
            user_message="",
            user_context={"user_id": 1},
            existing_memories=[]
        )
        assert result == []


class TestJudgeCore:
    """Test judge_core helper functions directly."""
    
    def test_parse_extraction_response_handles_store_field(self):
        """Test backward compatibility with 'store' field."""
        response = '{"memories": [{"key": "test", "value": "val", "store": true, "quality_score": 0.8}]}'
        memories = parse_extraction_response(response)
        assert memories[0]["should_store"] is True
        assert "store" not in memories[0]
    
    def test_filter_valid_memories_default_threshold(self):
        """Test default quality threshold is 0.7."""
        memories = [
            {"key": "a", "value": "1", "should_store": True, "quality_score": 0.7},
            {"key": "b", "value": "2", "should_store": True, "quality_score": 0.69},
            {"key": "c", "value": "3", "should_store": False, "quality_score": 0.9},
        ]
        filtered = filter_valid_memories(memories)
        assert len(filtered) == 1
        assert filtered[0]["key"] == "a"


def test_storage_decision_parse():
    """Test parsing of StorageDecision from JSON."""
    from src.memories.types import StorageDecision
    
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
