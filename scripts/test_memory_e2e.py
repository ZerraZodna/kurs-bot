"""
End-to-End Memory Functionality Test

Tests the complete memory extraction and storage pipeline:
1. User sends message with memory content
2. Memory extractor (Ollama) extracts structured data
3. MemoryManager stores in database
4. Memory can be retrieved later

Run this test with: python scripts/test_memory_e2e.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, Memory, init_db
from src.services.dialogue_engine import DialogueEngine
from src.services.memory_manager import MemoryManager
from datetime import datetime, timezone


def setup_test_user(db) -> int:
    """Create a test user and return user_id."""
    # Check if test user exists
    user = db.query(User).filter_by(external_id="test_user_memory").first()
    if not user:
        user = User(
            external_id="test_user_memory",
            channel="test",
            phone_number=None,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        print(f"✓ Created test user with ID: {user.user_id}")
    else:
        print(f"✓ Using existing test user with ID: {user.user_id}")
    
    return user.user_id


def clear_test_memories(db, user_id: int):
    """Clear existing memories for test user."""
    count = db.query(Memory).filter_by(user_id=user_id).delete()
    db.commit()
    print(f"✓ Cleared {count} existing memories")


def display_memories(db, user_id: int):
    """Display all memories for user."""
    memories = db.query(Memory).filter_by(user_id=user_id, is_active=True).all()
    
    if not memories:
        print("  (No memories found)")
        return
    
    for mem in memories:
        print(f"  • {mem.key}: {mem.value}")
        print(f"    - Confidence: {mem.confidence}")
        print(f"    - Source: {mem.source}")
        print(f"    - Created: {mem.created_at}")


async def test_memory_extraction_english():
    """Test memory extraction from English message."""
    print("\n" + "=" * 80)
    print("TEST 1: Memory Extraction (English)")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        init_db()
        user_id = setup_test_user(db)
        clear_test_memories(db, user_id)
        
        # Create dialogue engine
        dialogue = DialogueEngine(db)
        
        # Test message with memory content
        test_message = "My name is Johannes and my goal is to complete all 365 lessons of A Course in Miracles. I prefer to study in the morning."
        
        print(f"\nUser message: {test_message}")
        print("\nProcessing message...")
        
        # Process message (this should extract and store memories)
        response = await dialogue.process_message(
            user_id=user_id,
            text=test_message,
            session=db,
        )
        
        print(f"\nBot response: {response[:150]}...")
        
        # Check stored memories
        print("\n📝 Stored memories:")
        display_memories(db, user_id)
        
        # Verify memories were stored
        memories = db.query(Memory).filter_by(user_id=user_id, is_active=True).all()
        
        if len(memories) > 0:
            print(f"\n✅ SUCCESS: {len(memories)} memories extracted and stored!")
        else:
            print("\n❌ FAILED: No memories were stored")
            return False
        
        return True
        
    finally:
        db.close()


async def test_memory_extraction_norwegian():
    """Test memory extraction from Norwegian message."""
    print("\n" + "=" * 80)
    print("TEST 2: Memory Extraction (Norwegian)")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        user_id = setup_test_user(db)
        clear_test_memories(db, user_id)
        
        dialogue = DialogueEngine(db)
        
        test_message = "Jeg heter Emma og mitt mål er å lære meg programmering i Python. Jeg foretrekker å studere om kvelden."
        
        print(f"\nUser message: {test_message}")
        print("\nProcessing message...")
        
        response = await dialogue.process_message(
            user_id=user_id,
            text=test_message,
            session=db,
        )
        
        print(f"\nBot response: {response[:150]}...")
        
        print("\n📝 Stored memories:")
        display_memories(db, user_id)
        
        memories = db.query(Memory).filter_by(user_id=user_id, is_active=True).all()
        
        if len(memories) > 0:
            print(f"\n✅ SUCCESS: {len(memories)} memories extracted from Norwegian text!")
        else:
            print("\n❌ FAILED: No memories were stored")
            return False
        
        return True
        
    finally:
        db.close()


async def test_memory_retrieval():
    """Test that memories can be retrieved and used in context."""
    print("\n" + "=" * 80)
    print("TEST 3: Memory Retrieval and Context Usage")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        user_id = setup_test_user(db)
        
        # Store a test memory manually
        mm = MemoryManager(db)
        mm.store_memory(
            user_id=user_id,
            key="learning_goal",
            value="Master Python programming",
            confidence=1.0,
            source="test",
        )
        print("✓ Stored test memory: learning_goal = 'Master Python programming'")
        
        # Retrieve it
        memories = mm.get_memory(user_id, "learning_goal")
        
        print("\n📝 Retrieved memories:")
        for mem in memories:
            print(f"  • {mem['key']}: {mem['value']}")
            print(f"    - Confidence: {mem['confidence']}")
        
        if len(memories) > 0:
            print("\n✅ SUCCESS: Memory retrieval working!")
        else:
            print("\n❌ FAILED: Could not retrieve memory")
            return False
        
        return True
        
    finally:
        db.close()


async def test_memory_conflict_resolution():
    """Test that conflicting memories are handled correctly."""
    print("\n" + "=" * 80)
    print("TEST 4: Memory Conflict Resolution")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        user_id = setup_test_user(db)
        clear_test_memories(db, user_id)
        
        mm = MemoryManager(db)
        
        # Store initial memory
        print("Storing initial memory: learning_goal = 'Python'")
        mm.store_memory(user_id, "learning_goal", "Learn Python", confidence=1.0, source="test")
        
        # Store conflicting memory
        print("Storing conflicting memory: learning_goal = 'Machine Learning'")
        mm.store_memory(user_id, "learning_goal", "Learn Machine Learning", confidence=1.0, source="test")
        
        # Check active memory
        active_memories = mm.get_memory(user_id, "learning_goal")
        
        print("\n📝 Active memories:")
        for mem in active_memories:
            print(f"  • {mem['key']}: {mem['value']}")
        
        # Check archived memories
        archived = db.query(Memory).filter_by(
            user_id=user_id, 
            key="learning_goal",
            is_active=False
        ).all()
        
        print(f"\n📦 Archived memories: {len(archived)}")
        for mem in archived:
            print(f"  • {mem.value} (archived at {mem.archived_at})")
        
        if len(active_memories) == 1 and active_memories[0]['value'] == "Learn Machine Learning":
            print("\n✅ SUCCESS: Conflict resolution working! Old value archived, new value active.")
        else:
            print("\n❌ FAILED: Conflict resolution not working correctly")
            return False
        
        return True
        
    finally:
        db.close()


async def run_all_tests():
    """Run all memory tests."""
    print("\n" + "=" * 80)
    print("MEMORY FUNCTIONALITY TEST SUITE")
    print("=" * 80)
    print("\nMake sure Ollama is running with qwen2.5-coder:7b loaded!")
    print(f"Database: {Path('src/data/dev.db').absolute()}")
    
    results = []
    
    # Test 1: English extraction
    try:
        result = await test_memory_extraction_english()
        results.append(("English extraction", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("English extraction", False))
    
    # Test 2: Norwegian extraction
    try:
        result = await test_memory_extraction_norwegian()
        results.append(("Norwegian extraction", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Norwegian extraction", False))
    
    # Test 3: Memory retrieval
    try:
        result = await test_memory_retrieval()
        results.append(("Memory retrieval", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Memory retrieval", False))
    
    # Test 4: Conflict resolution
    try:
        result = await test_memory_conflict_resolution()
        results.append(("Conflict resolution", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Conflict resolution", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Memory system is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above for details.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
