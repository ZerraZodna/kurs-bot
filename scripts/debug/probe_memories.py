import asyncio

from src.config import settings
from src.memories.ai_judge import MemoryJudge


async def main():
    messages = [
        "I am born 23.05.1966",
        "I was born on 23.05.1966",
        "My birthday is 23.05.1966",
        "I was born 23 May 1966",
        "I was born on May 23, 1966",
    ]

    judge = MemoryJudge()
    print("Using RAG model:", settings.OLLAMA_MODEL)

    for msg in messages:
        print("\n=== MESSAGE ===")
        print(msg)
        res = await judge.extract_and_judge_memories(msg)
        print("=== EXTRACTED ===")
        print(res)


if __name__ == "__main__":
    asyncio.run(main())
