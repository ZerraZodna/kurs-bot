"""PromptRegistry — resolve which system prompt to use for RAG per-user.

Prototype implementation:
- Checks user memory `selected_rag_prompt_key` for a selected template key.
- If present and a matching `PromptTemplate` row exists, returns the template text.
- If the user has a custom prompt stored under memory key `custom_rag_prompt`, use that.
- Otherwise fall back to `settings.SYSTEM_PROMPT_RAG`.
"""
import logging
from typing import Optional
from src.models.database import PromptTemplate
from src.memories import MemoryManager
from src.memories.constants import MemoryKey
from src.models.database import SessionLocal
from src.config import settings

logger = logging.getLogger(__name__)


class PromptRegistry:
    def __init__(self, db=None):
        self.db = db or SessionLocal()

    def get_prompt_for_user(self, memory_manager: MemoryManager, user_id: int) -> str:
        """Resolve a RAG system prompt for a user.

        Order of resolution:
        1. `custom_rag_prompt` memory (free-text)
        2. `selected_rag_prompt_key` memory -> PromptTemplate lookup
        3. fallback `settings.SYSTEM_PROMPT_RAG`
        """
        try:
            # 1) custom prompt stored directly by user
            custom = memory_manager.get_memory(user_id, MemoryKey.CUSTOM_RAG_PROMPT)
            if custom:
                txt = custom[0].get("value")
                if txt and txt.strip():
                    return txt

            # 2) selected key referencing a template
            sel = memory_manager.get_memory(user_id, MemoryKey.SELECTED_RAG_PROMPT_KEY)
            if sel:
                key = sel[0].get("value")
                if key:
                    tmpl = self.db.query(PromptTemplate).filter(PromptTemplate.key == key).first()
                    if tmpl and tmpl.text:
                        return tmpl.text

        except Exception as e:
            logger.warning(f"PromptRegistry lookup failed for user {user_id}: {e}")

        # 3) default
        return settings.SYSTEM_PROMPT_RAG


_prompt_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    global _prompt_registry
    if _prompt_registry is None:
        _prompt_registry = PromptRegistry()
    return _prompt_registry
