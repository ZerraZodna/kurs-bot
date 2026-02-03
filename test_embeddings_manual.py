"""
Manual test for embeddings functionality
"""
import asyncio
from src.models.database import SessionLocal, User, init_db
from src.services.memory_manager import MemoryManager
from src.services.embedding_service import get_embedding_service
from src.services.semantic_search import get_semantic_search_service

async def test_embeddings():
    """Test embedding generation and semantic search"""
    
    # Initialize database
    init_db()
    session = SessionLocal()
    
    try:
        # Create test user if doesn't exist
        user = session.query(User).filter_by(user_id=1).first()
        if not user:
            user = User(
                user_id=1,
                external_id="test_user",
                channel="test",
                first_name="Test",
                last_name="User"
            )
            session.add(user)
            session.commit()
        
        print("✅ User created/found")
        
        # Test embedding service
        embedding_service = get_embedding_service()
        
        print("\n📊 Testing embedding generation...")
        embedding = await embedding_service.generate_embedding("I want to learn A Course in Miracles")
        
        if embedding:
            print(f"✅ Generated embedding with {len(embedding)} dimensions")
            print(f"   First 5 values: {embedding[:5]}")
        else:
            print("❌ Failed to generate embedding - is Ollama running?")
            print("   Run: ollama serve")
            return
        
        # Store memories with embeddings
        print("\n💾 Storing memories...")
        memory_manager = MemoryManager(session)
        
        memories_to_store = [
            ("learning_goal", "I want to complete all 365 lessons of ACIM", "goals"),
            ("practice_time", "I prefer to meditate in the morning", "preferences"),
            ("progress", "I finished lesson 50 today", "progress"),
            ("insight", "Forgiveness is the key to inner peace", "insights"),
        ]
        
        for key, value, category in memories_to_store:
            memory_id = memory_manager.store_memory(
                user_id=1,
                key=key,
                value=value,
                category=category,
                generate_embedding=False  # We'll do it manually
            )
            print(f"   Stored: {key} -> {value[:30]}...")
        
        session.commit()
        
        # Generate embeddings for all memories
        print("\n🔢 Generating embeddings for memories...")
        memories = session.query(User).filter_by(user_id=1).first().memories
        
        for memory in memories:
            if memory.is_active and not memory.embedding:
                embedding = await embedding_service.generate_embedding(memory.value)
                if embedding:
                    memory.embedding = embedding_service.embedding_to_bytes(embedding)
                    memory.embedding_version = 1
                    print(f"   ✅ Generated embedding for: {memory.key}")
        
        session.commit()
        
        # Refresh session to pick up new embeddings
        session.expire_all()
        
        # Test semantic search
        print("\n🔍 Testing semantic search...")
        search_service = get_semantic_search_service()
        
        queries = [
            "What are my spiritual goals?",
            "When do I like to practice?",
            "What insights have I gained?"
        ]
        
        for query in queries:
            print(f"\n   Query: '{query}'")
            results = await search_service.search_memories(
                user_id=1,
                query_text=query,
                session=session,
                limit=3
            )
            
            if results:
                for memory, score in results:
                    print(f"      Score {score:.3f}: {memory.value[:50]}...")
            else:
                print("      No results found")
        
        # Test cosine similarity
        print("\n📐 Testing similarity calculation...")
        query_embedding = await embedding_service.generate_embedding("spiritual practice")
        lesson_embedding = await embedding_service.generate_embedding("I want to complete all 365 lessons of ACIM")
        
        if query_embedding and lesson_embedding:
            similarity = embedding_service.cosine_similarity(query_embedding, lesson_embedding)
            print(f"   Similarity between 'spiritual practice' and 'lessons': {similarity:.3f}")
        
        print("\n🎉 All tests completed successfully!")
        
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_embeddings())
