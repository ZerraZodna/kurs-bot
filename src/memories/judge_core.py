"""Core logic for memory judgment and extraction.

Contains helper functions for parsing, context building, etc.
"""

import json
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def build_context_str(
    existing_memories: Optional[List[Any]],
    user_context: Optional[Dict[str, Any]]
) -> str:
    """Build context string from existing memories.
    
    Args:
        existing_memories: List of existing Memory objects or dicts
        user_context: Optional context dict (may include existing_memories)
    
    Returns:
        Context string for prompt injection
    """
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


def parse_extraction_response(response_text: str) -> List[Dict[str, Any]]:
    """Parse JSON response from Ollama extraction.
    
    Tries multiple parsing strategies:
    1. Direct JSON parse
    2. Extract from markdown code blocks
    3. Extract any JSON object
    
    Args:
        response_text: Raw response from Ollama
    
    Returns:
        List of memory dicts, or empty list if parsing fails
    """
    # Try direct JSON parse first
    try:
        data = json.loads(response_text)
        memories = data.get("memories", [])
        # Normalize: handle both "store" and "should_store" fields
        return [_normalize_memory(m) for m in memories]
    except json.JSONDecodeError:
        pass
    
    # Try extracting from markdown code blocks
    if "```json" in response_text:
        try:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end > start:
                data = json.loads(response_text[start:end].strip())
                memories = data.get("memories", [])
                return [_normalize_memory(m) for m in memories]
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Try generic markdown code blocks
    if "```" in response_text:
        try:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            if end > start:
                data = json.loads(response_text[start:end].strip())
                memories = data.get("memories", [])
                return [_normalize_memory(m) for m in memories]
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Try any JSON object in the response
    if "{" in response_text and "}" in response_text:
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            data = json.loads(response_text[start:end])
            memories = data.get("memories", [])
            return [_normalize_memory(m) for m in memories]
        except (json.JSONDecodeError, ValueError):
            pass
    
    logger.warning(f"Could not parse extraction response: {response_text[:100]}")
    return []


def _normalize_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize memory dict to always have 'should_store' field.
    
    Handles backward compatibility with old format that used 'store'.
    
    Args:
        memory: Raw memory dict from LLM
    
    Returns:
        Normalized memory dict with 'should_store' field
    """
    normalized = dict(memory)
    
    # Handle old format: "store" instead of "should_store"
    if "store" in normalized and "should_store" not in normalized:
        normalized["should_store"] = normalized["store"]
        del normalized["store"]
    
    # Ensure required fields exist
    if "should_store" not in normalized:
        normalized["should_store"] = False
    if "quality_score" not in normalized:
        normalized["quality_score"] = 0.0
    
    return normalized


def format_memories_for_prompt(memories: List[Any]) -> str:
    """Format memories for prompt context.
    
    Args:
        memories: List of Memory objects
    
    Returns:
        Formatted string for prompt injection
    """
    if not memories:
        return "  (none)"
    
    lines = []
    for m in memories:
        created = getattr(m, 'created_at', 'unknown')
        value_preview = m.value[:50] if hasattr(m, 'value') and m.value else ''
        lines.append(f"  - ID {m.memory_id}: {m.key}={value_preview}... (created: {created})")
    return "\n".join(lines)


def extract_json_from_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from response text.
    
    Args:
        response_text: Raw response from Ollama
    
    Returns:
        Parsed JSON dict, or None if extraction fails
    """
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


def filter_valid_memories(memories: List[Dict[str, Any]], min_quality: float = 0.7) -> List[Dict[str, Any]]:
    """Filter memories by quality threshold.
    
    Args:
        memories: List of memory dicts
        min_quality: Minimum quality_score to include
    
    Returns:
        List of valid memories with high quality
    """
    valid_memories = [
        m for m in memories
        if m.get("should_store") 
        and m.get("key")
        and m.get("quality_score", 0) >= min_quality
    ]
    
    # Use cleaned_value if available
    for m in valid_memories:
        if m.get("cleaned_value"):
            m["value"] = m["cleaned_value"]
    
    return valid_memories
