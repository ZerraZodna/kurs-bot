"""
List top-N memories for a user using semantic embeddings (RAG helper).

Usage:
  python scripts/rag_memory.py --user 1 --query "my recent thoughts" --top 20

If `--query` is omitted the script will list the most recent memories that have
embeddings for the given user (ordered by `embedding_generated_at`).
"""
import argparse
import asyncio
import os
import sys

# Ensure project root on path when invoked as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.models.database import SessionLocal, Memory
from src.services.semantic_search import get_semantic_search_service
# Embeddings are no longer persisted on Memory; rely on vector index / semantic search


def truncate(s: str, n: int = 200) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def main(user_id: int, query: str | None, top: int = 20):
    session = SessionLocal()
    try:
        def _print_memories(mems: list):
            for mem in mems:
                date = getattr(mem, "created_at", None)
                date_short = date.strftime("%Y-%m-%d %H:%M") if date is not None else "-"
                key = getattr(mem, "key", "")
                key_part = f" {key}" if key else ""
                print(f"{date_short}: {mem.category}{key_part}: \"{truncate(mem.value)}\"")

        # If query is provided and is not '*' run a semantic search; otherwise
        # list the complete set of memories (with embeddings) for the user
        if query and query.strip() and query.strip() != "*":
            svc = get_semantic_search_service()
            # run async search
            results = asyncio.run(svc.search_memories(user_id=user_id, query_text=query, session=session, limit=top))
            if not results:
                print("No results for query")
                return
            _print_memories([m for (m, s) in results])
        else:
            # List the complete set of memories, oldest first
            q = (
                session.query(Memory)
                .filter(Memory.user_id == user_id)
                .filter(Memory.is_active == True)
                .order_by(Memory.created_at.asc())
            )
            rows = q.all()
            if not rows:
                print("No memories found for user", user_id)
                return
            _print_memories(rows)
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", type=int, required=False, help="User ID (default from CURRENT_USER_ID env or 1)")
    parser.add_argument("--query", type=str, required=False, help="Query text to run semantic search with")
    parser.add_argument("--top", type=int, default=20, help="Number of results to return")
    args = parser.parse_args()

    env_user = None
    try:
        env_user = int(os.getenv("CURRENT_USER_ID"))
    except Exception:
        env_user = None

    user_id = args.user or env_user or 1

    main(user_id=user_id, query=args.query, top=args.top)
