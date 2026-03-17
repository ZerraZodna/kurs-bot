"""Topic-based memory retrieval and storage with temporal resolution.

Provides AI-friendly structured access to memories organized by topics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from src.core.timezone import utc_now
from typing import Dict, List, Any


from src.memories.manager import MemoryManager
from src.memories.topics import (
    MemoryTopic, 
    TopicData, 
    TopicField, 
    TopicFieldValue,
    resolve_canonical_key,
    get_all_keys_for_topic,
)

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
                source=current_mem.get("source", "unknown"),
                updated_at=current_mem.get("created_at") or utc_now(),
                original_key=current_mem["key"],
            )
            
            # History is the rest (older values)
            history = []
            for old_mem in sorted_memories[1:]:
                history.append(TopicFieldValue(
                    value=old_mem["value"],
                    source=old_mem.get("source", "unknown"),
                    updated_at=old_mem.get("created_at") or utc_now(),
                    original_key=old_mem["key"],
                ))
            
            topic_data.fields[field_name] = TopicField(
                canonical_name=field_name,
                current=current,
                history=history,
            )
        
        return topic_data
        
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
