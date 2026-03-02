"""Topic-based memory retrieval and storage with temporal resolution.

Provides AI-friendly structured access to memories organized by topics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union

from sqlalchemy.orm import Session

from src.memories.manager import MemoryManager
from src.memories.topics import (
    MemoryTopic, 
    TopicData, 
    TopicField, 
    TopicFieldValue,
    resolve_canonical_key,
    get_all_keys_for_topic,
    get_all_fields_for_topic,
    CANONICAL_KEY_MAP,
)
from src.memories.constants import MemoryCategory

logger = logging.getLogger(__name__)


class TopicManager:
    """Manages topic-based memory retrieval and storage."""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
    
    def get_topic(self, user_id: int, topic: MemoryTopic) -> TopicData:
        """Retrieve all memories for a topic, organized by canonical fields.
        
        For each field, returns the most recent value with full history.
        """
        # Get all key synonyms for this topic
        topic_keys = get_all_keys_for_topic(topic)
        
        # Fetch all memories for these keys
        all_memories = []
        for key in topic_keys:
            memories = self.memory_manager.get_memory(user_id, key)
            for mem in memories:
                all_memories.append({
                    "key": key,
                    "value": mem["value"],
                    "confidence": mem.get("confidence", 1.0),
                    "source": mem.get("source", "unknown"),
                    "created_at": mem.get("created_at"),
                    "memory_id": mem.get("memory_id"),
                })
        
        # Group by canonical field
        field_memories: Dict[str, List[dict]] = {}
        for mem in all_memories:
            resolved = resolve_canonical_key(mem["key"])
            if not resolved:
                continue
            _, canonical_field = resolved
            if canonical_field not in field_memories:
                field_memories[canonical_field] = []
            field_memories[canonical_field].append(mem)
        
        # Build TopicData with temporal resolution (newest wins)
        topic_data = TopicData(topic=topic)
        
        for field_name, memories in field_memories.items():
            # Sort by created_at descending (newest first)
            sorted_memories = sorted(
                memories, 
                key=lambda x: x.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )
            
            if not sorted_memories:
                continue
            
            # Current value is the newest
            current_mem = sorted_memories[0]
            current = TopicFieldValue(
                value=current_mem["value"],
                confidence=current_mem.get("confidence", 1.0),
                source=current_mem.get("source", "unknown"),
                updated_at=current_mem.get("created_at") or datetime.now(timezone.utc),
                original_key=current_mem["key"],
            )
            
            # History is the rest (older values)
            history = []
            for old_mem in sorted_memories[1:]:
                history.append(TopicFieldValue(
                    value=old_mem["value"],
                    confidence=old_mem.get("confidence", 1.0),
                    source=old_mem.get("source", "unknown"),
                    updated_at=old_mem.get("created_at") or datetime.now(timezone.utc),
                    original_key=old_mem["key"],
                ))
            
            topic_data.fields[field_name] = TopicField(
                canonical_name=field_name,
                current=current,
                history=history,
            )
        
        return topic_data
    
    def get_field(self, user_id: int, canonical_field: str) -> Optional[TopicField]:
        """Get a specific canonical field across all topics."""
        # Find which topic this field belongs to
        for topic in MemoryTopic:
            if canonical_field in get_all_fields_for_topic(topic):
                topic_data = self.get_topic(user_id, topic)
                return topic_data.fields.get(canonical_field)
        return None
    
    def get_field_value(self, user_id: int, canonical_field: str) -> Optional[Any]:
        """Get the current value of a specific field."""
        field = self.get_field(user_id, canonical_field)
        if field:
            return field.current.value
        return None
    
    def store_topic_field(
        self, 
        user_id: int, 
        key: str,  # Can be any synonym
        value: Any,
        confidence: float = 1.0,
        source: str = "dialogue_engine",
        category: str = MemoryCategory.PROFILE.value,
    ) -> int:
        """Store a memory, resolving the key to its canonical topic/field.
        
        The key can be any synonym (e.g., "first_name", "name", "full_name").
        It will be stored with the original key but resolved to canonical field
        for retrieval.
        """
        # Resolve to canonical
        resolved = resolve_canonical_key(key)
        if resolved:
            topic, canonical_field = resolved
            logger.debug(f"Resolved key '{key}' to topic={topic.value}, field={canonical_field}")
        else:
            # Unknown key - store as-is
            logger.warning(f"Unknown key '{key}', storing without topic resolution")
        
        # Store with the original key (preserves what AI/user said)
        # The retrieval logic will resolve it to canonical field
        return self.memory_manager.store_memory(
            user_id=user_id,
            key=key,  # Store with original key
            value=str(value),
            confidence=confidence,
            source=source,
            category=category,
            allow_duplicates=False,  # Will archive old value, keep history via conflict_group_id
        )
    
    def get_all_topics(self, user_id: int) -> Dict[MemoryTopic, TopicData]:
        """Retrieve all topics with their data for a user."""
        return {
            topic: self.get_topic(user_id, topic)
            for topic in MemoryTopic
        }
    
    def get_ai_context(self, user_id: int, topics: Optional[List[MemoryTopic]] = None) -> Dict[str, Any]:
        """Generate AI-friendly structured context for specified topics.
        
        Returns a nested dict suitable for injection into prompts.
        """
        if topics is None:
            topics = list(MemoryTopic)
        
        context = {}
        for topic in topics:
            topic_data = self.get_topic(user_id, topic)
            if topic_data.fields:  # Only include non-empty topics
                context[topic.value] = topic_data.to_dict()["fields"]
        
        return context
    
    def get_name(self, user_id: int) -> str:
        """Get the user's name with proper temporal resolution.
        
        This fixes the bug where old Telegram "Dev" was used instead of 
        newer user-provided "Johannes".
        """
        # Get identity topic - will return most recent name across all synonyms
        identity = self.get_topic(user_id, MemoryTopic.IDENTITY)
        
        if "name" in identity.fields:
            return str(identity.fields["name"].current.value)
        
        # Fallback to any name-related memory
        name_keys = ["first_name", "name", "full_name"]
        all_names = []
        for key in name_keys:
            memories = self.memory_manager.get_memory(user_id, key)
            for mem in memories:
                all_names.append({
                    "value": mem["value"],
                    "created_at": mem.get("created_at"),
                })
        
        if all_names:
            # Sort by created_at descending, return newest
            sorted_names = sorted(
                all_names,
                key=lambda x: x.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )
            return str(sorted_names[0]["value"])
        
        return "friend"  # Ultimate fallback
    
    def get_profile_context(self, user_id: int, user: Any = None) -> Dict[str, Any]:
        """Get consolidated profile context for prompt building.
        
        Returns a dict with all profile fields, combining topic-based
        memories with user object fallbacks.
        """
        context = {}
        
        # Get name with temporal resolution
        name = self.get_name(user_id)
        if name and name != "friend":
            context["name"] = name
        elif user and user.first_name:
            context["name"] = f"{user.first_name} {user.last_name or ''}".strip()
        
        # Get all identity fields from topic
        identity = self.get_topic(user_id, MemoryTopic.IDENTITY)
        for field_name, value in identity.get_all_fields().items():
            if field_name != "name":  # Already handled above
                context[field_name] = value
        
        # Add user object fallbacks for missing fields
        if user:
            if "email" not in context and user.email:
                context["email"] = user.email
            if "phone" not in context and user.phone_number:
                context["phone"] = user.phone_number
        
        return context
