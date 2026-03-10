"""Unit tests for Memory Judge (AI-powered memory extraction).

Migrated from MemoryExtractor to MemoryJudge.
MemoryJudge combines extraction + quality validation in a single Ollama call.
"""

import pytest
import os

from src.memories.ai_judge import MemoryJudge


@pytest.fixture
def judge():
    """Create a MemoryJudge instance for testing."""
    return MemoryJudge()


class TestMemoryJudgeExtraction:
    """MemoryJudge extraction unit tests."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    async def test_extract_memories_english(self, judge):
        """Test memory extraction from English text."""
        # Given: An English message with a goal
        message = "My goal is to learn Python programming. I prefer to study in the morning."
        
        # When: Extracting memories
        memories = await judge.extract_and_judge_memories(message)
        
        # Then: Should extract at least one high-quality memory with a goal
        assert len(memories) > 0
        goals = [m for m in memories if "goal" in m.get("key", "").lower()]
        assert len(goals) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    async def test_extract_memories_norwegian(self, judge):
        """Test memory extraction from Norwegian text."""
        # Given: A Norwegian message
        message = "Mitt mål er å lære Python-programmering. Jeg foretrekker å studere om morgenen."
        
        # When: Extracting memories
        memories = await judge.extract_and_judge_memories(message)
        
        # Then: Should extract at least one high-quality memory
        assert len(memories) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    async def test_extract_memories_empty(self, judge):
        """Test extraction from casual/empty messages."""
        # Given: A casual greeting message
        message = "Hi, how are you?"
        
        # When: Extracting memories
        memories = await judge.extract_and_judge_memories(message)
        
        # Then: Casual greeting should not extract memories
        # LLM doesn't extract memories from casual greetings
        assert len(memories) == 0

    def test_parse_json_response_markdown(self, judge):
        """Test JSON parsing from markdown-wrapped response."""
        # Given: A markdown-wrapped JSON response
        response = '''Some text before
```json
{"memories": [{"store": true, "key": "goal", "value": "learn"}]}
```
Some text after'''
        
        # When: Parsing the response
        memories = judge._parse_extraction_response(response)
        
        # Then: Should correctly extract the memory from markdown
        assert len(memories) == 1
        assert memories[0]["key"] == "goal"
