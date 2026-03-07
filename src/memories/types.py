"""Type definitions for memory extraction and judgment."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any, TypeVar

# Import Memory model for type hints
from src.models.memory import Memory

# Type alias for Memory model
MemoryEntity = Memory

# Type alias for memory record dictionary
MemoryRecord = Dict[str, Any]


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


@dataclass
class ExtractedMemory:
    """A memory extracted from user message."""
    key: str
    value: str
    cleaned_value: Optional[str] = None
    quality_score: float = 0.0
    should_store: bool = False
    confidence: float = 0.0
    reasoning: str = ""
    conflicts: List[ConflictDecision] = None
    
    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedMemory":
        """Create from dictionary (parsed from LLM JSON response)."""
        conflicts = []
        for c in data.get("conflicts", []):
            conflicts.append(ConflictDecision(
                existing_memory_id=c.get("existing_memory_id", 0),
                reason=c.get("reason", ""),
                action=c.get("action", "FLAG"),
                existing_value=c.get("existing_value")
            ))
        
        return cls(
            key=data.get("key", ""),
            value=data.get("value", ""),
            cleaned_value=data.get("cleaned_value"),
            quality_score=data.get("quality_score", 0.0),
            should_store=data.get("should_store", False),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            conflicts=conflicts
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "key": self.key,
            "value": self.value,
            "cleaned_value": self.cleaned_value,
            "quality_score": self.quality_score,
            "should_store": self.should_store,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "conflicts": [
                {
                    "existing_memory_id": c.existing_memory_id,
                    "reason": c.reason,
                    "action": c.action,
                    "existing_value": c.existing_value
                }
                for c in self.conflicts
            ]
        }

