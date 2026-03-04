"""
AI-powered memory extraction and validation.
Combines extraction + quality validation in a single Ollama call.
Replaces MemoryExtractor to avoid double Ollama calls.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from src.config import settings

logger = logging.getLogger(__name__)

# Combined extraction + validation prompt
MEMORY_EXTRACTION_JUDGE_PROMPT = """You are a personal memory system. Extract facts from user messages and validate their quality.

EXTRACTION RULES:
1. Extract explicit facts: name, goals, preferences, commitments
2. Store long-term goals, learning objectives, personal preferences
3. Only store sensitive info with explicit consent
4. Skip casual chit-chat, questions, vague statements
5. Work in any language - Norwegian, English, etc.
6. Prefer user corrections over inferred information

COMMON KEYS:
- "first_name": User's first/given name (ALWAYS use this key for any name)
- "learning_goal": What they want to learn/achieve
- "preferred_lesson_time": When they want lessons (morning, evening, 9:00 AM, etc.)
- "acim_commitment": Commitment to ACIM lessons
- "current_lesson": Lesson number they're on (numeric)
- "lesson_completed": Lesson number they finished (numeric)
- "email": Email address
- "phone": Phone number
- "birth_date": User's birth date. When you detect an explicit birth date, store it under this key.
    - Prefer ISO 8601 date format (YYYY-MM-DD) in the `value` when possible.
    - Accept and parse common formats such as `DD.MM.YYYY`, `D M YYYY`, `Month D, YYYY`, `YYYY-MM-DD`.
    - Example: "I was born on 23.05.1966" -> {"store": true, "key": "birth_date", "value": "1966-05-23", "confidence": 0.98}

VALIDATION RULES:
- quality_score: 0.0-1.0 based on clarity and certainty
- cleaned_value: extract just the fact, remove extra text
- should_store: false if corrupted, nonsensical, or already known
- Reject values like "No, my full name is spelled backwards sennahoJ" → cleaned: "Johannes"

Output ONLY valid JSON:
{
  "memories": [
    {
      "key": "first_name",
      "value": "raw extracted value",
      "cleaned_value": "cleaned value or null",
      "quality_score": 0.0-1.0,
      "should_store": true/false,
      "confidence": 0.0-1.0,
      "reasoning": "brief explanation"
    }
  ]
}

Empty if nothing to store: {"memories": []}

User message: "{user_message}"
{context_str}"""


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
    Single AI interface for memory extraction AND validation.
    Replaces MemoryExtractor to avoid double Ollama calls.
    """
    
    def __init__(self, ollama_client=None):
        self.ollama_client = ollama_client
        self._cache = {}  # Simple in-memory cache for decisions
    
    async def extract_and_judge_memories(
        self,
        user_message: str,
        user_context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract AND validate memories in a single Ollama call.
        Replaces MemoryExtractor.extract_memories().
        
        Returns only high-quality memories (quality_score >= 0.7).
        """
        if not user_message or len(user_message.strip()) < 3:
            return []
        
        try:
            # Build context string
            context_str = ""
            if user_context:
                existing = user_context.get("existing_memories", {})
                if existing:
                    context_str = f"\nUser's existing memories: {json.dumps(existing)}"
            
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
            
            # Use cleaned_value if available
            for m in valid_memories:
                if m.get("cleaned_value"):
                    m["value"] = m["cleaned_value"]
            
            logger.debug(f"Extracted {len(valid_memories)} high-quality memories from: {user_message[:50]}")
            return valid_memories
            
        except Exception as e:
            logger.error(f"Error in extract_and_judge: {e}")
            return []
    
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
        """
        # Check cache
        cache_key = f"{user_id}:{proposed_key}:{proposed_value}:{user_message}"
        if cache_key in self._cache:
            logger.debug(f"MemoryJudge cache hit for {proposed_key}")
            return self._cache[cache_key]
        
        memory_context = self._format_memories(existing_memories)
        
        prompt = f"""You are a memory system judge. Evaluate this proposed memory storage.

USER MESSAGE: "{user_message}"

PROPOSED MEMORY:
  key: {proposed_key}
  value: {proposed_value}

EXISTING USER MEMORIES:
{memory_context}

Evaluate and respond in JSON:
{{
  "should_store": true/false,
  "quality_score": 0.0-1.0,
  "issues": ["list any problems"],
  "cleaned_value": "cleaned version or null",
  "conflicts": [
    {{
      "existing_memory_id": 123,
      "reason": "why this conflicts",
      "action": "REPLACE|KEEP_BOTH|MERGE|FLAG",
      "existing_value": "value of existing memory"
    }}
  ],
  "reasoning": "brief explanation"
}}

Rules:
- should_store=false if value is corrupted, nonsensical, or already known
- cleaned_value: extract just the fact if value contains extra text
- conflicts: identify ANY memory referring to the same concept (any key)
- action=REPLACE when new is correction/update
- action=KEEP_BOTH when genuinely different facts
- action=MERGE when combining gives better result
- action=FLAG when uncertain

Examples of conflicts:
- "first_name=Bob" vs "name=Robert" → same person, different keys
- "email=old@example.com" vs "email=new@example.com" → same concept, updated
- "lesson_current=5" vs "lesson_completed=5" → different concepts

Examples of corrupted values:
- "No, my full name is spelled backwards sennahoJ" → cleaned: "Johannes"
- "I think maybe around 5 or 6 lessons" → cleaned: "5-6" or null"""

        try:
            # Lazy import to avoid circular dependencies
            from src.services.dialogue.ollama_client import call_ollama
            from src.config import settings
            
            # Use settings (conftest.py handles TEST_* env var overrides)
            model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL
            response_text = await call_ollama(prompt, model=model)
            
            # Parse JSON from response
            try:
                # Try to extract JSON if wrapped in markdown
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                elif "```" in response_text:
                    start = response_text.find("```") + 3
                    end = response_text.find("```", start)
                    json_str = response_text[start:end].strip()
                else:
                    # Find first { and last }
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    json_str = response_text[start:end]
                
                data = json.loads(json_str)
                decision = StorageDecision.parse(data)
                
                # Cache the decision
                self._cache[cache_key] = decision
                
                logger.info(f"MemoryJudge: {proposed_key} → quality={decision.quality_score}, store={decision.should_store}")
                logger.debug(f"MemoryJudge reasoning: {decision.reasoning}")
                
                return decision
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AI judge response: {e}")
                logger.error(f"Response: {response_text[:200]}")
                # Fallback: allow storage with warning
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
            # Fallback: allow storage
            return StorageDecision(
                should_store=True,
                quality_score=0.5,
                issues=[f"AI judge error: {e}"],
                cleaned_value=None,
                conflicts=[],
                reasoning="AI judge unavailable, fallback to allow"
            )
    
    async def find_relevant_memories(
        self,
        query: str,
        memories: List[Any],
        context: Optional[str] = None
    ) -> List[int]:
        """
        AI selects relevant memories for a query.
        """
        if not memories:
            return []
        
        memory_context = self._format_memories(memories)
        
        prompt = f"""Select memories relevant to this query.

QUERY: "{query}"
CONTEXT: "{context or 'None'}"

MEMORIES:
{memory_context}

Return JSON:
{{
  "selected_ids": [123, 456],
  "reasoning": "why selected",
  "confidence": 0.0-1.0
}}

Select ALL memories that answer the query. If multiple conflict, select most recent."""

        try:
            from src.services.dialogue.ollama_client import call_ollama
            from src.config import settings
            
            # Use settings (conftest.py handles TEST_* env var overrides)
            model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL
            response_text = await call_ollama(prompt, model=model)
            
            # Extract JSON
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            else:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
            
            data = json.loads(json_str)
            return data.get("selected_ids", [])
            
        except Exception as e:
            logger.error(f"Memory retrieval AI call failed: {e}")
            return [m.memory_id for m in memories]
