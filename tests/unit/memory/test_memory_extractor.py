"""Unit tests for Memory Extractor service.

Migrated from tests/test_memory_extractor.py to use new test fixtures.
"""

import pytest
import asyncio

from src.memories.memory_extractor import MemoryExtractor


class TestMemoryExtractor:
    """Memory extractor unit tests."""

    @pytest.mark.asyncio
    async def test_extract_memories_english(self):
        """Test memory extraction from English text."""
        # Given: An English message with a goal
        message = "My goal is to learn Python programming. I prefer to study in the morning."
        
        # When: Extracting memories
        memories = await MemoryExtractor.extract_memories(message)
        
        # Then: Should extract at least one memory with a goal
        assert len(memories) > 0
        goals = [m for m in memories if "goal" in m.get("key", "").lower()]
        assert len(goals) > 0

    @pytest.mark.asyncio
    async def test_extract_memories_norwegian(self):
        """Test memory extraction from Norwegian text."""
        # Given: A Norwegian message
        message = "Mitt mål er å lære Python-programmering. Jeg foretrekker å studere om morgenen."
        
        # When: Extracting memories
        memories = await MemoryExtractor.extract_memories(message)
        
        # Then: Should extract at least one memory
        assert len(memories) > 0

    @pytest.mark.asyncio
    async def test_extract_memories_empty(self):
        """Test extraction from casual/empty messages."""
        # Given: A casual greeting message
        message = "Hi, how are you?"
        
        # When: Extracting memories
        memories = await MemoryExtractor.extract_memories(message)
        
        # Then: Casual greeting should not extract memories
        assert len(memories) == 0

    @pytest.mark.asyncio
    async def test_extract_memories_with_context(self):
        """Test extraction with existing user context."""
        # Given: A message that corrects a previous memory
        message = "Actually, my goal is machine learning, not Python."
        context = {
            "existing_memories": {
                "learning_goal": "Python programming"
            }
        }
        
        # When: Extracting memories with context
        memories = await MemoryExtractor.extract_memories(message, context)
        
        # Then: Should recognize the correction and extract new goal
        assert len(memories) > 0

    @pytest.mark.asyncio
    async def test_parse_json_response_direct(self):
        """Test JSON parsing from direct response."""
        # Given: A direct JSON response
        response = '{"memories": [{"store": true, "key": "test", "value": "value", "confidence": 0.9, "ttl_hours": null}]}'
        
        # When: Parsing the response
        memories = MemoryExtractor._parse_ollama_response(response)
        
        # Then: Should correctly extract the memory
        assert len(memories) == 1
        assert memories[0]["key"] == "test"

    @pytest.mark.asyncio
    async def test_parse_json_response_markdown(self):
        """Test JSON parsing from markdown-wrapped response."""
        # Given: A markdown-wrapped JSON response
        response = '''Some text before
```json
{"memories": [{"store": true, "key": "goal", "value": "learn", "confidence": 0.95, "ttl_hours": null}]}
```
Some text after'''
        
        # When: Parsing the response
        memories = MemoryExtractor._parse_ollama_response(response)
        
        # Then: Should correctly extract the memory from markdown
        assert len(memories) == 1
        assert memories[0]["key"] == "goal"

