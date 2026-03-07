"""
AI-powered memory extraction and validation.
Combines extraction + quality validation + conflict detection in a single Ollama call.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from src.config import settings
from src.memories.prompts import MEMORY_EXTRACTION_JUDGE_PROMPT, STORAGE_EVALUATION_PROMPT, MEMORY_RELEVANCE_PROMPT
from src.memories.cache import DecisionCache

logger = logging.getLogger(__name__)


@dataclass
class ConflictDecision:
    """Decision about a conflicting memory."""
    existing_memory_id: int
    reason: str
    action: str  # REPLACE, KEEP_BOTH, MERGE, FLAG
    existing_value: Optional[str] = None


@dataclass
class StorageDecision:
    """AI's decision about storing a memory."""
    should_store: bool
    quality_score: float
    issues: List[str]
    cleaned_value: Optional[str]
    conflicts: List[ConflictDecision]
    reasoning: str
    
    @classmethod
    def parse(cls, response: Dict[str, Any]) -> "StorageDecision":
        """Parse JSON response from LLM."""
        conflicts = []
        for c in response.get("conflicts", []):
            conflicts.append(ConflictDecision(
                existing_memory_id=c.get("existing_memory_id", 0),
                reason=c.get("reason", ""),
                action=c.get("action", "FLAG"),
                existing_value=c.get("existing_value")
            ))
        
        return cls(
            should_store=response.get("should_store", False),
            quality_score=response.get("quality_score", 0.0),
            issues=response.get("issues", []),
            cleaned_value=response.get("cleaned_value"),
            conflicts=conflicts,
            reasoning=response.get("reasoning", "No reasoning provided")
        )


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
            context_str = self._build_context_str(existing_memories, user_context)
            
            # Build prompt
            prompt = MEMORY_EXTRACTION_JUDGE_PROMPT.format(
                user_message=user_message,
                context_str=context_str
            )
            
            # Call Ollama once
            from src.services.dialogue.ollama_client import call_ollama
            model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL
            response_text = await call_ollama(prompt, model=model, language=language)
            
            # Parse response
            memories = self._parse_extraction_response(response_text)
            
            # Filter: only return high-quality memories
            valid_memories = [
                m for m in memories
                if m.get("should_store") 
                and m.get("key")
                and m.get("quality_score", 0) >= 0.7
            ]
            
            # Log extraction results
            user_id_str = user_context.get('user_id') if user_context else 'N/A'
            logger.info(
                f"MemoryJudge.extract_and_judge: user_id={user_id_str}, "
                f"extracted={len(memories)}, valid={len(valid_memories)}, "
                f"message={user_message[:50]!r}..."
            )
            
            # Use cleaned_value if available
            for m in valid_memories:
                if m.get("cleaned_value"):
                    m["value"] = m["cleaned_value"]
            
            logger.debug(f"Extracted {len(valid_memories)} high-quality memories from: {user_message[:50]}")
            return valid_memories
            
        except Exception as e:
            logger.error(f"Error in extract_and_judge: {e}")
            return []
    
    def _build_context_str(
        self,
        existing_memories: Optional[List[Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build context string from existing memories."""
        context_str = ""
        
        # Use existing_memories parameter if provided
        if existing_memories is not None and len(existing_memories) > 0:
            existing_list = []
            for m in existing_memories:
                # Support both Memory objects and dicts
                if hasattr(m, 'memory_id'):
                    existing_list.append({
                        "memory_id": m.memory_id,
                        "key": m.key,
                        "value": m.value,
                        "category": getattr(m, 'category', 'fact')
                    })
                elif isinstance(m, dict):
                    existing_list.append({
                        "memory_id": m.get('memory_id', 0),
                        "key": m.get('key', ''),
                        "value": m.get('value', ''),
                        "category": m.get('category', 'fact')
                    })
            
            if existing_list:
                context_str = f"\nUser's existing memories: {json.dumps(existing_list)}"
        elif user_context:
            # Fallback to user_context for backward compatibility
            existing = user_context.get("existing_memories", {})
            if existing:
                context_str = f"\nUser's existing memories: {json.dumps(existing)}"
        
        return context_str
    
    def _parse_extraction_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse JSON response from Ollama extraction."""
        # Try direct JSON parse
        try:
            data = json.loads(response_text)
            return data.get("memories", [])
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown
        if "```json" in response_text:
            try:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    data = json.loads(response_text[start:end].strip())
                    return data.get("memories", [])
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Try any JSON object
        if "{" in response_text and "}" in response_text:
            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                data = json.loads(response_text[start:end])
                return data.get("memories", [])
            except (json.JSONDecodeError, ValueError):
                pass
        
        logger.warning(f"Could not parse extraction response: {response_text[:100]}")
        return []
    
    def _format_memories(self, memories: List[Any]) -> str:
        """Format memories for prompt context."""
        if not memories:
            return "  (none)"
        
        lines = []
        for m in memories:
            created = getattr(m, 'created_at', 'unknown')
            lines.append(f"  - ID {m.memory_id}: {m.key}={m.value[:50]}... (created: {created})")
        return "\n".join(lines)
    
    async def evaluate_storage(
        self,
        user_id: int,
        proposed_key: str,
        proposed_value: str,
        user_message: str,
        existing_memories: List[Any]
    ) -> StorageDecision:
        """
        AI decides: Should we store this? What conflicts exist? What action?
        Uses persistent caching.
        """
        # Check cache
        cache_key = f"{user_id}:{proposed_key}:{proposed_value}:{user_message}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"MemoryJudge cache hit for {proposed_key}")
            return StorageDecision.parse(cached)
        
        memory_context = self._format_memories(existing_memories)
        
        prompt = STORAGE_EVALUATION_PROMPT.format(
            user_message=user_message,
            proposed_key=proposed_key,
            proposed_value=proposed_value,
            memory_context=memory_context
        )
        
        try:
            from src.services.dialogue.ollama_client import call_ollama
            from src.config import settings
            
            model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL
            response_text = await call_ollama(prompt, model=model)
            
            # Parse JSON from response
            data = self._extract_json(response_text)
            if data:
                decision = StorageDecision.parse(data)
                # Cache the decision
                self._cache.set(cache_key, {
                    "should_store": decision.should_store,
                    "quality_score": decision.quality_score,
                    "issues": decision.issues,
                    "cleaned_value": decision.cleaned_value,
                    "conflicts": [
                        {
                            "existing_memory_id": c.existing_memory_id,
                            "reason": c.reason,
                            "action": c.action,
                            "existing_value": c.existing_value
                        }
                        for c in decision.conflicts
                    ],
                    "reasoning": decision.reasoning
                })
                logger.info(f"MemoryJudge: {proposed_key} → quality={decision.quality_score}, store={decision.should_store}")
                return decision
            
            # Fallback if parse failed
            return StorageDecision(
                should_store=True,
                quality_score=0.5,
                issues=["AI judge parse failed, allowing with caution"],
                cleaned_value=None,
                conflicts=[],
                reasoning="Parse error, fallback to allow"
            )
                
        except Exception as e:
            logger.error(f"AI judge call failed: {e}")
            return StorageDecision(
                should_store=True,
                quality_score=0.5,
                issues=[f"AI judge error: {e}"],
                cleaned_value=None,
                conflicts=[],
                reasoning="AI judge unavailable, fallback to allow"
            )
    
    def _extract_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from response text."""
        # Try to extract JSON if wrapped in markdown
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end > start:
                return json.loads(response_text[start:end].strip())
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            if end > start:
                return json.loads(response_text[start:end].strip())
        else:
            # Find first { and last }
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response_text[start:end])
        
        return None
    
    async def find_relevant_memories(
        self,
        query: str,
        memories: List[Any],
        context: Optional[str] = None
    ) -> List[int]:
        """AI selects relevant memories for a query."""
        if not memories:
            return []
        
        memory_context = self._format_memories(memories)
        
        prompt = MEMORY_RELEVANCE_PROMPT.format(
            query=query,
            context=context or "None",
            memory_context=memory_context
        )
        
        try:
            from src.services.dialogue.ollama_client import call_ollama
            from src.config import settings
            
            model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL
            response_text = await call_ollama(prompt, model=model)
            
            data = self._extract_json(response_text)
            if data:
                return data.get("selected_ids", [])
            
        except Exception as e:
            logger.error(f"Memory retrieval AI call failed: {e}")
        
        return [m.memory_id for m in memories]

