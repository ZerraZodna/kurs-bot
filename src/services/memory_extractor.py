"""
Memory Extractor Service: Uses Ollama LLM to intelligently extract and classify
user memories from conversation messages. Language-agnostic (English, Norwegian, etc).
"""

import json
import httpx
from typing import Optional, Dict, Any, List
from src.config import settings
import logging

logger = logging.getLogger(__name__)

OLLAMA_URL = settings.OLLAMA_URL or "http://localhost:11434/api/generate"
MEMORY_EXTRACTOR_MODEL = settings.MEMORY_EXTRACTOR_MODEL or "qwen2.5-coder:7b"

# System prompt for memory extraction - language agnostic
MEMORY_EXTRACTION_PROMPT = """You are a personal memory classifier. Your job is to extract meaningful facts and preferences from user messages.

Rules:
1. Always extract explicit facts: name, goals, preferences, commitment statements
2. Store long-term goals, learning objectives, and personal preferences
3. Only store sensitive info (health, financial) with explicit consent
4. Skip casual chit-chat, questions, and vague statements
5. Work in any language - Norwegian, English, etc.
6. Prefer user corrections (e.g., "actually my goal is X") over inferred information

Output ONLY valid JSON (no markdown, no code blocks). Example:
{"memories": [{"store": true, "key": "learning_goal", "value": "Learn Python programming", "confidence": 0.95, "ttl_hours": null}]}

Empty if nothing to store:
{"memories": []}

Now extract memories from this message:
"""


class MemoryExtractor:
    """Extract user memories from messages using Ollama LLM."""

    @staticmethod
    async def extract_memories(
        user_message: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract memories from a user message using Ollama.
        
        Args:
            user_message: The user's message text
            user_context: Optional context about the user (previous memories, etc)
        
        Returns:
            List of memory objects: [{store, key, value, confidence, ttl_hours}, ...]
        """
        if not user_message or len(user_message.strip()) < 3:
            return []
        
        try:
            # Build context string if provided
            context_str = ""
            if user_context:
                existing_memories = user_context.get("existing_memories", {})
                if existing_memories:
                    context_str = f"\n\nUser's existing memories: {json.dumps(existing_memories)}"
            
            # Build full prompt
            prompt = f"""{MEMORY_EXTRACTION_PROMPT}
User message: "{user_message}"{context_str}"""
            
            # Call Ollama
            payload = {
                "model": MEMORY_EXTRACTOR_MODEL,
                "prompt": prompt,
                "stream": False,
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                response_text = data.get("response", "").strip()
            
            # Parse JSON response
            memories = MemoryExtractor._parse_ollama_response(response_text)
            
            # Filter and validate
            valid_memories = [
                m for m in memories
                if m.get("store") and m.get("key") and m.get("value")
            ]
            
            logger.debug(f"Extracted {len(valid_memories)} memories from message: {user_message[:50]}")
            return valid_memories
            
        except Exception as e:
            logger.error(f"Error extracting memories: {e}")
            return []

    @staticmethod
    def _parse_ollama_response(response_text: str) -> List[Dict[str, Any]]:
        """
        Parse JSON response from Ollama. Handles cases where Ollama wraps JSON in markdown.
        
        Args:
            response_text: Raw response from Ollama
        
        Returns:
            List of memory dicts or empty list if parsing fails
        """
        # Try direct JSON parse first
        try:
            data = json.loads(response_text)
            return data.get("memories", [])
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code blocks
        if "```json" in response_text:
            try:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    json_str = response_text[start:end].strip()
                    data = json.loads(json_str)
                    return data.get("memories", [])
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Try extracting any JSON-like object
        if "{" in response_text and "}" in response_text:
            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if end > start:
                    json_str = response_text[start:end]
                    data = json.loads(json_str)
                    return data.get("memories", [])
            except (json.JSONDecodeError, ValueError):
                pass
        
        logger.warning(f"Could not parse memory extraction response: {response_text[:100]}")
        return []

    @staticmethod
    async def extract_memories_batch(
        messages: List[str],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract memories from multiple messages.
        
        Args:
            messages: List of user messages
            user_context: Optional context about the user
        
        Returns:
            Dict mapping message -> list of memories
        """
        results = {}
        for msg in messages:
            results[msg] = await MemoryExtractor.extract_memories(msg, user_context)
        return results
