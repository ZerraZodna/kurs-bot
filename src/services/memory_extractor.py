"""
Memory Extractor Service: Uses Ollama LLM to intelligently extract and classify
user memories from conversation messages. Language-agnostic (English, Norwegian, etc).
"""

import json
from typing import Optional, Dict, Any, List
from src.config import settings
import logging

logger = logging.getLogger(__name__)

DEFAULT_RAG_MODEL = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None) or settings.OLLAMA_MODEL

# System prompt for memory extraction - language agnostic
MEMORY_EXTRACTION_PROMPT = """You are a personal memory classifier. Your job is to extract meaningful facts and preferences from user messages.

Rules:
1. Always extract explicit facts: name, goals, preferences, commitment statements
2. Store long-term goals, learning objectives, and personal preferences
3. Only store sensitive info (health, financial) with explicit consent
4. Skip casual chit-chat, questions, and vague statements
5. Work in any language - Norwegian, English, etc.
6. Prefer user corrections (e.g., "actually my goal is X") over inferred information
7. COMMITMENT DETECTION: Look for statements where users commit to doing lessons regularly (e.g., "Ja, jeg ønsker", "Yes, I want", "ready to commit", "I'll do it daily", "jeg har lyst")
8. LESSON PROGRESS: Extract when user mentions what lesson they're on or have completed

Common memory keys to use:
- "first_name": User's first/given name (ALWAYS use this key for any name, even short ones like "Jo", "Li", "Live", "Max")
- "name": Only use for full name if both first and last name are provided together
- "learning_goal": What they want to learn/achieve
- "preferred_lesson_time": When they want lessons/reminders (e.g., "morning", "9:00 AM", "evening", "daily")
- "acim_commitment": If they commit to ACIM lessons (store "committed to 365 ACIM lessons" or similar commitment phrase)
- "current_lesson": The lesson number they're currently on (e.g., "2", "15", "100")
- "lesson_completed": When they finish/complete a lesson (store just the lesson number)
- "study_preference": How they prefer to study
- "email": Email address
- "phone": Phone number
- "birth_date": User's birth date. When you detect an explicit birth date, store it under this key.
    - Prefer ISO 8601 date format (YYYY-MM-DD) in the `value` when possible.
    - Accept and parse common formats such as `DD.MM.YYYY`, `D M YYYY`, `Month D, YYYY`, `YYYY-MM-DD`.
    - Example: "I was born on 23.05.1966" -> {"store": true, "key": "birth_date", "value": "1966-05-23", "confidence": 0.98}

IMPORTANT: If a date is present in the message, prefer storing it under the `birth_date` key rather than `name` or `first_name`.

LESSON PROGRESS EXAMPLES:
- "I am currently on lesson 2" -> {"store": true, "key": "current_lesson", "value": "2", "confidence": 0.95}
- "I just finished lesson 5" -> {"store": true, "key": "lesson_completed", "value": "5", "confidence": 0.95}
- "jeg er på leksjon 10" -> {"store": true, "key": "current_lesson", "value": "10", "confidence": 0.95}
- "I'm working on lesson 23" -> {"store": true, "key": "current_lesson", "value": "23", "confidence": 0.95}

COMMITMENT EXAMPLES (extract as "acim_commitment"):
- English: "Yes, I'm ready to commit to this journey!" -> store "committed to ACIM lessons"
- Norwegian: "Ja, jeg ønsker gjøre leksene hver dag" -> store "committed to daily ACIM lessons"
- Norwegian: "jeg har lyst å bli kjent med deg" -> NO commitment (just wanting to get to know the coach)
- English: "I want to start learning" -> store "committed to learning ACIM"

Output ONLY valid JSON (no markdown, no code blocks). Example:
{"memories": [{"store": true, "key": "first_name", "value": "Sarah", "confidence": 0.98, "ttl_hours": null}]}

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
        model_override: Optional[str] = None,
        language: Optional[str] = None,
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
            
            # Call Ollama via shared client wrapper, include language hint
            model = model_override or settings.OLLAMA_CHAT_RAG_MODEL
            # Lazy import to avoid circular imports during package initialization
            from src.services.dialogue.ollama_client import call_ollama
            response_text = await call_ollama(prompt, model=model, language=language)
            
            # Parse JSON response
            memories = MemoryExtractor._parse_ollama_response(response_text)

            # Filter and validate
            valid_memories = [
                m for m in memories
                if m.get("store") and m.get("key") and m.get("value")
            ]

            # If Ollama returned nothing useful, fall back to simple heuristics
            if not valid_memories:
                heur = MemoryExtractor._heuristic_extract(user_message, existing_memories if user_context else None)
                if heur:
                    logger.debug(f"Heuristic extracted {len(heur)} memories from message")
                    return heur

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
    def _heuristic_extract(message: str, existing_memories: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Lightweight heuristic extractor used when Ollama is unavailable.
        Targets common patterns for learning goals and preferred lesson times
        in English and simple Norwegian phrases.
        """
        out: List[Dict[str, Any]] = []
        msg = message.strip()
        lower = msg.lower()

        # Common single-word confirmations we should NOT treat as names
        confirmations = {"yes", "no", "ja", "nei", "ok", "okay", "sure", "yep", "nope", "si", "sí"}
        if lower in confirmations:
            logger.debug("Heuristic skipped confirmation-like single-word message")
            return out

        # Common single-word greetings we should NOT treat as names
        greetings = {"hi", "hei", "hej", "hello", "hallo", "hey"}
        if lower in greetings:
            logger.debug("Heuristic skipped greeting-like single-word message")
            return out

        # Heuristic: single-word capitalized names (e.g., "Live", "Jo")
        words = msg.split()
        if 1 <= len(words) <= 2 and all(w.isalpha() for w in words) and words[0][0].isupper():
            # Do not overwrite existing first_name
            if existing_memories and existing_memories.get("first_name"):
                logger.debug("Heuristic would extract a first_name but user already has one; skipping")
                return out
            # Avoid saving common confirmations as names (already handled above), save as first_name
            out.append({"store": True, "key": "first_name", "value": words[0], "confidence": 0.9, "ttl_hours": None})
            return out

        # Detect learning goal phrases (English/Norwegian)
        import re
        goal_patterns = [r"my goal is to (.+)", r"i want to (.+)", r"jeg ønsker(?: å| å)?(?: )?(?:lære|gjøre|bli) (.+)", r"lære (.+)"]
        for pat in goal_patterns:
            m = re.search(pat, lower)
            if m:
                val = m.group(1).strip().rstrip(".")
                out.append({"store": True, "key": "learning_goal", "value": val, "confidence": 0.75, "ttl_hours": None})
                break

        # Detect preferred lesson time (morning/evening/time strings)
        time_keywords = {
            "morning": ["morning", "morgenen", "morgenen", "om morgenen", "morgen"],
            "evening": ["evening", "evenings", "aften", "om kvelden", "kveld"],
            "night": ["night", "nighttime", "natt"]
        }
        for canonical, kws in time_keywords.items():
            for kw in kws:
                if kw in lower:
                    out.append({"store": True, "key": "preferred_lesson_time", "value": canonical, "confidence": 0.8, "ttl_hours": None})
                    break
            if any(kw in lower for kw in kws):
                break

        return out

