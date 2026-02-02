#!/usr/bin/env python
"""Test memory extraction"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.memory_extractor import MemoryExtractor

async def test():
    message = "Ja, jeg ønsker gjøre leksene hver dag. Kan du minne meg på det?"
    
    print("=" * 80)
    print("MEMORY EXTRACTION TEST")
    print("=" * 80)
    print(f"\nMessage: {message}")
    print("\nExtracting memories...")
    
    memories = await MemoryExtractor.extract_memories(message)
    
    print(f"\nExtracted {len(memories)} memories:")
    for mem in memories:
        print(f"  Key: {mem.get('key')}")
        print(f"  Value: {mem.get('value')}")
        print(f"  Confidence: {mem.get('confidence')}")
        print()

asyncio.run(test())
