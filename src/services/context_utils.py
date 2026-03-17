"""Memory categories and context utilities."""

from typing import List

# Re-export for test compatibility
try:
    from src.memories.constants import MemoryCategory, MemoryKey
except Exception:
    # Defensive fallback for import-time issues
    MemoryCategory = None  # type: ignore[misc]
    MemoryKey = None  # type: ignore[misc]



class ConversationContextBuilder:
    """Helpers for building multi-turn conversation context."""
    
    @staticmethod
    def format_conversation_turn(user_msg: str, assistant_msg: str) -> str:
        """Format a single conversation exchange."""
        return f"User: {user_msg}\n\nAssistant: {assistant_msg}"
    

class ContextOptimizer:
    """Utility helpers for estimating tokens and preparing context text for prompts.

    These methods use simple, deterministic heuristics suitable for tests and
    coarse token-based truncation rather than a full tokenizer.
    """

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Return a rough token estimate using a characters->token heuristic.

        Heuristic used in tests: ~4 characters per token.
        """
        if not text:
            return 0
        return max(0, len(text) // 4)

    @staticmethod
    def truncate_by_tokens(text: str, max_tokens: int) -> str:
        """Truncate `text` so it is roughly within `max_tokens` using the
        same 4-chars-per-token heuristic. Truncation tries to avoid cutting
        a word in half by trimming to the last space if possible.
        """
        if not text:
            return ""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        # Truncate and try to keep whole words
        truncated = text[:max_chars]
        # If next char is not whitespace and there is a space in truncated,
        # trim back to the last space to avoid splitting words.
        if not truncated.endswith(" ") and " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return truncated

    @staticmethod
    def format_memory_list(memories: List[dict], max_items: int = 5) -> str:
        """Format a list of memory dicts for inclusion in a prompt.

        Each memory is expected to be a dict with key `value`.
        Returns up to `max_items` lines.
        """
        if not memories:
            return ""
        lines = []
        for m in memories[:max_items]:
            value = m.get("value", "")
            lines.append(f"{value}")
        return "\n".join(lines)

