"""
AI-powered memory extraction and validation.
Combines extraction + quality validation + conflict detection in a single Ollama call.

Refactored to use separate modules:
- types.py: Data classes (ConflictDecision, StorageDecision, ExtractedMemory)
- judge_core.py: Helper functions for parsing and context building
- cache.py: Persistent caching for AI judgments
"""

import logging
from typing import List, Optional, Dict, Any

from src.config import settings
from src.memories.prompts import MEMORY_EXTRACTION_JUDGE_PROMPT
from src.memories.cache import DecisionCache
from src.memories.types import StorageDecision, ConflictDecision
from src.memories.judge_core import (
    build_context_str,
    parse_extraction_response,
    format_memories_for_prompt,
    extract_json_from_response,
    filter_valid_memories,
)

logger = logging.getLogger(__name__)


class MemoryJudge:
    """
    Single AI interface for memory extraction, validation, and conflict detection.
    Uses unified prompts to minimize Ollama calls.
    """
    
    def __init__(self, ollama_client=None):
        self.ollama_client = ollama_client
        self._cache = DecisionCache()
    
    def invalidate_cache_for_key(self, user_id: int, key: str) -> None:
        """Invalidate all cache entries for a specific user and key."""
        self._cache.invalidate_for_key(user_id, key)
    
    def clear_cache(self) -> None:
        """Clear all cached decisions."""
        self._cache.clear()
    
    async def extract_and_judge_memories(
        self,
        user_message: str,
        user_context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
        existing_memories: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract AND validate memories in a single Ollama call.
        Also detects conflicts with existing memories when provided.
        
        Args:
            user_message: The user's message to extract memories from
            user_context: Optional context dict (may include user_id)
            language: Optional language hint for Ollama
            existing_memories: List of existing Memory objects for conflict detection
        
        Returns:
            List of dicts with extracted memories including conflict info.
        """
        if not user_message or len(user_message.strip()) < 3:
            return []
        
        try:
            # Build context string with existing memories
            context_str = build_context_str(existing_memories, user_context)
            
            # Build prompt
            prompt = MEMORY_EXTRACTION_JUDGE_PROMPT.format(
                user_message=user_message,
                context_str=context_str
            )
            
            # Call Ollama once
            from src.services.dialogue.ollama_client import call_ollama
            model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL
            response_text = await call_ollama(prompt, model=model, language=language)
            
            # Parse response - now handles both "store" and "should_store"
            memories = parse_extraction_response(response_text)
            
            # Filter: only return high-quality memories
            valid_memories = filter_valid_memories(memories)
            
            # Log extraction results
            user_id_str = user_context.get('user_id') if user_context else 'N/A'
            logger.info(
                f"MemoryJudge.extract_and_judge: user_id={user_id_str}, "
                f"extracted={len(memories)}, valid={len(valid_memories)}, "
                f"message={user_message[:50]!r}..."
            )
            
            logger.debug(f"Extracted {len(valid_memories)} high-quality memories from: {user_message[:50]}")
            return valid_memories
            
        except Exception as e:
            logger.error(f"Error in extract_and_judge: {e}")
            return []
    
    def _parse_extraction_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse JSON response from Ollama extraction.
        
        This is a wrapper around the judge_core.parse_extraction_response function
        to allow direct testing of the parsing logic.
        
        Args:
            response_text: Raw response from Ollama
        
        Returns:
            List of memory dicts, or empty list if parsing fails
        """
        return parse_extraction_response(response_text)

