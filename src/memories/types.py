"""Type definitions for memory extraction."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# Import Memory model for type hints
from src.models.memory import Memory

# Type alias for Memory model
MemoryEntity = Memory

# Type alias for memory record dictionary
MemoryRecord = Dict[str, Any]


@dataclass
class ExtractedMemory:
    """A memory extracted from user message."""
    key: str
    value: str
    cleaned_value: Optional[str] = None
    reasoning: str = ""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedMemory":
        
        return cls(
            key=data.get("key", ""),
            value=data.get("value", ""),
            cleaned_value=data.get("cleaned_value"),
            reasoning=data.get("reasoning", "")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "key": self.key,
            "value": self.value,
            "cleaned_value": self.cleaned_value,
            "reasoning": self.reasoning
        }

