"""
Tests for the Memory Extractor service
"""

import pytest
import asyncio
from src.memories.memory_extractor import MemoryExtractor


@pytest.mark.asyncio
async def test_extract_memories_english():
    """Test memory extraction from English text."""
    message = "My goal is to learn Python programming. I prefer to study in the morning."
    memories = await MemoryExtractor.extract_memories(message)
    
    assert len(memories) > 0
    # Should extract learning goal
    goals = [m for m in memories if "goal" in m.get("key", "").lower()]
    assert len(goals) > 0


@pytest.mark.asyncio
async def test_extract_memories_norwegian():
    """Test memory extraction from Norwegian text."""
    message = "Mitt mål er å lære Python-programmering. Jeg foretrekker å studere om morgenen."
    memories = await MemoryExtractor.extract_memories(message)
    
    assert len(memories) > 0


@pytest.mark.asyncio
async def test_extract_memories_empty():
    """Test extraction from casual/empty messages."""
    message = "Hi, how are you?"
    memories = await MemoryExtractor.extract_memories(message)
    
    # Casual greeting should not extract memories
    assert len(memories) == 0


@pytest.mark.asyncio
async def test_extract_memories_with_context():
    """Test extraction with existing user context."""
    message = "Actually, my goal is machine learning, not Python."
    context = {
        "existing_memories": {
            "learning_goal": "Python programming"
        }
    }
    memories = await MemoryExtractor.extract_memories(message, context)
    
    # Should recognize the correction and extract new goal
    assert len(memories) > 0


@pytest.mark.asyncio
async def test_parse_json_response_direct():
    """Test JSON parsing from direct response."""
    response = '{"memories": [{"store": true, "key": "test", "value": "value", "confidence": 0.9, "ttl_hours": null}]}'
    memories = MemoryExtractor._parse_ollama_response(response)
    
    assert len(memories) == 1
    assert memories[0]["key"] == "test"


@pytest.mark.asyncio
async def test_parse_json_response_markdown():
    """Test JSON parsing from markdown-wrapped response."""
    response = '''Some text before
```json
{"memories": [{"store": true, "key": "goal", "value": "learn", "confidence": 0.95, "ttl_hours": null}]}
```
Some text after'''
    memories = MemoryExtractor._parse_ollama_response(response)
    
    assert len(memories) == 1
    assert memories[0]["key"] == "goal"


if __name__ == "__main__":
    # Manual test
    async def run_manual_test():
        print("Testing memory extraction...")
        
        # Test 1: English
        msg = "My name is John and my goal is to learn Spanish"
        memories = await MemoryExtractor.extract_memories(msg)
        print(f"\nEnglish: {msg}")
        print(f"Extracted: {memories}")
        
        # Test 2: Norwegian
        msg_no = "Jeg heter Emma og jeg vil lære meg programmering"
        memories_no = await MemoryExtractor.extract_memories(msg_no)
        print(f"\nNorwegian: {msg_no}")
        print(f"Extracted: {memories_no}")
        
        # Test 3: Casual
        msg_casual = "Hey, what's up?"
        memories_casual = await MemoryExtractor.extract_memories(msg_casual)
        print(f"\nCasual: {msg_casual}")
        print(f"Extracted: {memories_casual}")
    
    asyncio.run(run_manual_test())
