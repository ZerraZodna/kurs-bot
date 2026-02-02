"""Quick test to see what memories are being extracted"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.memory_extractor import MemoryExtractor


async def test_extractions():
    """Test what memories get extracted from test messages."""
    
    test_cases = [
        "My name is Sarah",
        "Yes, I'm ready to commit to this journey!",
        "I prefer to receive lessons at 9:00 AM",
    ]
    
    for msg in test_cases:
        print(f"\n{'='*60}")
        print(f"Message: {msg}")
        print(f"{'='*60}")
        
        memories = await MemoryExtractor.extract_memories(msg)
        
        if memories:
            for mem in memories:
                print(f"  ✓ {mem.get('key')}: {mem.get('value')}")
                print(f"    Confidence: {mem.get('confidence')}")
        else:
            print("  (No memories extracted)")


if __name__ == "__main__":
    asyncio.run(test_extractions())
