"""
Test semantic search with threshold adjustment
"""
import asyncio
from src.models.database import SessionLocal
from src.services.semantic_search import get_semantic_search_service

async def test_search():
    session = SessionLocal()
    search_service = get_semantic_search_service()
    
    query = "What are my spiritual goals?"
    print(f"🔍 Searching: '{query}'\n")
    
    # Try with low threshold
    results = await search_service.search_memories(
        user_id=1,
        query_text=query,
        session=session,
        threshold=0.0,  # Accept any result
        limit=10
    )
    
    if results:
        print(f"Found {len(results)} results:")
        for memory, score in results:
            print(f"  Score {score:.4f}: [{memory.category}] {memory.value[:60]}...")
    else:
        print("No results found")
    
    session.close()

if __name__ == "__main__":
    asyncio.run(test_search())
