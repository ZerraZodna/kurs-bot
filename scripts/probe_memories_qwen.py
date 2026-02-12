import asyncio
from src.memories.memory_extractor import MemoryExtractor
from src.config import settings


async def main():
    messages = [
        "I am born 23.05.1966",
        "I was born on 23.05.1966",
        "My birthday is 23.05.1966",
        "I was born 23 May 1966",
        "I was born on May 23, 1966",
    ]

    print("Using model:", settings.OLLAMA_MODEL)
    for msg in messages:
        print("\n=== MESSAGE ===")
        print(msg)
        res = await MemoryExtractor.extract_memories(msg, model_override=settings.OLLAMA_MODEL)
        print("=== EXTRACTED ===")
        print(res)


if __name__ == '__main__':
    asyncio.run(main())
