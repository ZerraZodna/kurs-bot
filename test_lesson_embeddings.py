"""
Test semantic search on ACIM lessons
"""
import asyncio
from src.models.database import SessionLocal, Lesson
from src.services.embedding_service import get_embedding_service

async def index_lessons():
    """Generate embeddings for all lessons"""
    session = SessionLocal()
    embedding_service = get_embedding_service()
    
    print("📚 Indexing ACIM lessons with embeddings...\n")
    
    lessons = session.query(Lesson).all()
    print(f"Found {len(lessons)} lessons to index")
    
    # Generate embeddings for first 10 lessons as a test
    for i, lesson in enumerate(lessons[:10], 1):
        # Combine title and content for embedding
        text_to_embed = f"{lesson.title}\n\n{lesson.content[:500]}"
        
        print(f"  {i}. Generating embedding for Lesson {lesson.lesson_id}...")
        embedding = await embedding_service.generate_embedding(text_to_embed)
        
        if embedding:
            print(f"     ✅ Generated {len(embedding)}-dim embedding")
        else:
            print(f"     ❌ Failed")
    
    print(f"\n🎉 Indexed {min(10, len(lessons))} lessons!")
    session.close()

if __name__ == "__main__":
    asyncio.run(index_lessons())
