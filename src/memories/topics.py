"""Topic-based memory organization for AI-friendly structured retrieval.

Organizes memories into topics with sub-fields, enabling temporal resolution
and canonical key mapping. Similar to lesson_state pattern but generalized
for all memory types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class MemoryTopic(str, Enum):
    """Top-level memory topics."""
    IDENTITY = "identity"
    PREFERENCES = "preferences"


# Canonical key mappings: synonym -> (topic, canonical_field)
# AI can use any synonym, system resolves to canonical field within topic
CANONICAL_KEY_MAP: Dict[str, tuple[MemoryTopic, str]] = {
    # Identity topic
    "first_name": (MemoryTopic.IDENTITY, "name"),
    "name": (MemoryTopic.IDENTITY, "name"),
    "full_name": (MemoryTopic.IDENTITY, "name"),
    "last_name": (MemoryTopic.IDENTITY, "last_name"),
    "email": (MemoryTopic.IDENTITY, "email"),
    "phone": (MemoryTopic.IDENTITY, "phone"),
    "birth_date": (MemoryTopic.IDENTITY, "birth_date"),
    "personal_background": (MemoryTopic.IDENTITY, "background"),
    "background": (MemoryTopic.IDENTITY, "background"),
        
    # Preferences topic
    "preferred_lesson_time": (MemoryTopic.PREFERENCES, "preferred_lesson_time"),
    "lesson_time": (MemoryTopic.PREFERENCES, "preferred_lesson_time"),
    "reminder_time": (MemoryTopic.PREFERENCES, "preferred_lesson_time"),
        
    "learning_style": (MemoryTopic.PREFERENCES, "learning_style"),
    "preferred_tone": (MemoryTopic.PREFERENCES, "preferred_tone"),
    "tone": (MemoryTopic.PREFERENCES, "preferred_tone"),
    "user_language": (MemoryTopic.PREFERENCES, "user_language"),
    "language": (MemoryTopic.PREFERENCES, "user_language"),
    "data_consent": (MemoryTopic.PREFERENCES, "data_consent"),
}


@dataclass
class TopicFieldValue:
    """A single value within a topic field with metadata."""
    value: Any
    source: str
    updated_at: datetime
    original_key: str  # The key used when storing (e.g., "first_name" or "name")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "original_key": self.original_key,
        }


@dataclass
class TopicField:
    """A field within a topic, containing current value and history."""
    canonical_name: str
    current: TopicFieldValue
    history: List[TopicFieldValue] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.current.value,
            "updated_at": self.current.updated_at.isoformat() if self.current.updated_at else None,
            "source": self.current.source,
            "original_key": self.current.original_key,
            "history": [h.to_dict() for h in self.history] if self.history else None,
        }


@dataclass
class TopicData:
    """Complete data for a topic with all its fields."""
    topic: MemoryTopic
    fields: Dict[str, TopicField] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic.value,
            "fields": {
                name: field.to_dict() 
                for name, field in self.fields.items()
            }
        }
        
    def get_all_fields(self) -> Dict[str, Any]:
        """Get all field values as a simple dict for easy iteration."""
        return {
            name: field.current.value 
            for name, field in self.fields.items()
        }


def resolve_canonical_key(key: str) -> Optional[tuple[MemoryTopic, str]]:
    """Resolve any key synonym to its canonical (topic, field) tuple.
    
    Returns None if key is not recognized.
    """
    key_lower = key.lower().strip()
    return CANONICAL_KEY_MAP.get(key_lower)


def get_topic_for_key(key: str) -> Optional[MemoryTopic]:
    """Get the topic for a given key synonym."""
    resolved = resolve_canonical_key(key)
    if resolved:
        return resolved[0]
    return None


def get_all_keys_for_topic(topic: MemoryTopic) -> List[str]:
    """Get all key synonyms that map to a given topic."""
    keys = []
    for key, (t, _field) in CANONICAL_KEY_MAP.items():
        if t == topic:
            keys.append(key)
    return keys
