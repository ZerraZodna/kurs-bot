"""
Function Registry for ACIM Course Bot.

Defines all available functions that the AI can call, including their
metadata, parameters, and validation schemas.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ParameterType(Enum):
    """Supported parameter types for function calls."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TIME = "time"  # HH:MM format
    TIMEZONE = "timezone"  # IANA timezone name


@dataclass
class ParameterSchema:
    """Schema for a function parameter."""
    name: str
    description: str
    type: ParameterType
    required: bool = True
    default: Optional[Any] = None
    examples: List[str] = field(default_factory=list)
    
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a parameter value with type coercion for common cases."""
        if value is None:
            if self.required:
                return False, f"Required parameter '{self.name}' is missing"
            return True, None
        
        # Type validation with tolerance for common AI mistakes
        if self.type == ParameterType.STRING:
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be a string"
        elif self.type == ParameterType.INTEGER:
            # Allow string numbers to be parsed and float values that are whole numbers
            if isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be an integer"
            if isinstance(value, str):
                try:
                    parsed = float(value)
                    if not parsed.is_integer():
                        return False, f"Parameter '{self.name}' must be an integer"
                except (ValueError, TypeError):
                    return False, f"Parameter '{self.name}' must be an integer"
            elif isinstance(value, float):
                if not value.is_integer():
                    return False, f"Parameter '{self.name}' must be an integer"
            elif not isinstance(value, int):
                return False, f"Parameter '{self.name}' must be an integer"
        elif self.type == ParameterType.NUMBER:
            # Lenient numeric validation for LLM-generated values (int/float/numeric strings)
            if isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be a number"
            if isinstance(value, str):
                try:
                    float(value)
                except (ValueError, TypeError):
                    return False, f"Parameter '{self.name}' must be a number"
            elif not isinstance(value, (int, float)):
                return False, f"Parameter '{self.name}' must be a number"
        elif self.type == ParameterType.BOOLEAN:
            # Be tolerant: accept string "true"/"false" or numeric 0/1
            if isinstance(value, bool):
                return True, None
            if isinstance(value, str):
                if value.lower() in ("true", "false"):
                    return True, None
                if value in ("0", "1"):
                    return True, None
            return False, f"Parameter '{self.name}' must be a boolean"
        elif self.type == ParameterType.TIME:
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be a time string (HH:MM)"
            # Basic time format validation
            if not self._is_valid_time(value):
                return False, f"Parameter '{self.name}' must be in HH:MM format"
        elif self.type == ParameterType.TIMEZONE:
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be a timezone string"
        elif self.type == ParameterType.DATETIME:
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be an ISO datetime string"
        
        return True, None
    
    def _is_valid_time(self, time_str: str) -> bool:
        """Check if time string is valid HH:MM format."""
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError):
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for prompt generation."""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "required": self.required,
            "default": self.default,
            "examples": self.examples,
        }


@dataclass
class FunctionMetadata:
    """Metadata for an available function."""
    name: str
    description: str
    parameters: List[ParameterSchema]
    examples: List[Dict[str, Any]] = field(default_factory=list)
    contexts: List[str] = field(default_factory=lambda: ["general_chat"])
    
    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate all parameters for this function.
        
        Note: This validation is tolerant of unknown parameters - extra parameters
        that are not defined in the schema are ignored to allow AI flexibility.
        """
        errors = []
        
        # Get known parameters from schema
        known_params = {p.name for p in self.parameters}
        
        # Log unknown parameters but don't error - be tolerant of AI flexibility
        unknown_params = set(params.keys()) - known_params
        if unknown_params:
            logger.debug(f"Ignoring unknown parameters for {self.name}: {unknown_params}")
        
        # Validate each parameter that is in the schema
        for schema in self.parameters:
            value = params.get(schema.name)
            is_valid, error = schema.validate(value)
            if not is_valid:
                errors.append(error)
        
        return len(errors) == 0, errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for prompt generation."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "examples": self.examples,
        }
    
    def to_prompt_text(self) -> str:
        """Generate prompt text describing this function."""
        lines = [f"- {self.name}: {self.description}"]

        required = [p for p in self.parameters if p.required]
        optional = [p for p in self.parameters if not p.required]
        
        if required:
            for param in required:
                lines.append(f"    - {param.name} ({param.type.value}): {param.description}")
        if optional:
            opt_names = ", ".join(f"{p.name}?" for p in optional)
            lines.append(f"    - optional: {opt_names}")

        return "\n".join(lines)


class FunctionRegistry:
    """Registry of all available functions."""
    
    def __init__(self):
        self._functions: Dict[str, FunctionMetadata] = {}
        self._register_default_functions()
    
    def _register_default_functions(self):
        """Register all default functions."""
        # Scheduling functions
        self.register(FunctionMetadata(
            name="create_schedule",
            description="Create a daily recurring schedule for lesson reminders",
            parameters=[
                ParameterSchema(
                    name="time",
                    description="24-hour format time",
                    type=ParameterType.TIME,
                    required=True,
                    examples=["09:00", "14:30", "20:00"],
                ),
                ParameterSchema(
                    name="message",
                    description="Message to send with the reminder",
                    type=ParameterType.STRING,
                    required=False,
                    default="Time for your ACIM lesson",
                ),
                ParameterSchema(
                    name="lesson_id",
                    description="Specific lesson ID to start with (optional)",
                    type=ParameterType.INTEGER,
                    required=False,
                ),
            ],
            examples=[
                {"time": "09:00", "message": "Good morning! Time for your lesson"},
                {"time": "20:00"},
            ],
            contexts=["general_chat", "schedule_setup", "onboarding"],
        ))
        
        self.register(FunctionMetadata(
            name="update_schedule",
            description="Update an existing schedule's time",
            parameters=[
                ParameterSchema(
                    name="schedule_id",
                    description="Schedule ID",
                    type=ParameterType.INTEGER,
                    required=True,
                ),
                ParameterSchema(
                    name="time",
                    description="New time for the reminder",
                    type=ParameterType.TIME,
                    required=True,
                    examples=["08:00", "15:30"],
                ),
            ],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="delete_schedule",
            description="Delete a schedule",
            parameters=[
                ParameterSchema(
                    name="schedule_id",
                    description="Schedule ID",
                    type=ParameterType.INTEGER,
                    required=True,
                ),
            ],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="query_schedule",
            description="List all user's schedules and reminders",
            parameters=[],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="create_one_time_reminder",
            description="Create a one-time reminder at a specific time",
            parameters=[
                ParameterSchema(
                    name="run_at",
                    description="ISO datetime (e.g. 2024-01-15T09:00:00)",
                    type=ParameterType.DATETIME,
                    required=True,
                    examples=["2024-01-15T09:00:00", "2024-01-15T14:30:00"],
                ),
                ParameterSchema(
                    name="message",
                    description="Message text",
                    type=ParameterType.STRING,
                    required=True,
                    examples=["Lesson reminder", "Time to review"],
                ),
            ],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="delete_one_time_reminder",
            description="Delete a specific one-time reminder by its schedule ID",
            parameters=[
                ParameterSchema(
                    name="schedule_id",
                    description="Schedule ID",
                    type=ParameterType.INTEGER,
                    required=True,
                ),
            ],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="delete_all_one_time_reminders",
            description="Delete all one-time reminders for the user",
            parameters=[],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="delete_all_daily_reminders",
            description="Delete all daily recurring reminders for the user",
            parameters=[],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="delete_all_reminders",
            description="Delete all reminders (both daily and one-time) for the user",
            parameters=[],
            contexts=["general_chat", "schedule_setup"],
        ))
        
        # Lesson functions
        self.register(FunctionMetadata(
            name="send_lesson",
            description="Send a specific lesson to the user",
            parameters=[
                ParameterSchema(
                    name="lesson_id",
                    description="Lesson ID",
                    type=ParameterType.INTEGER,
                    required=True,
                    examples=[1, 42, 365],
                ),
            ],
            contexts=["general_chat", "lesson_review"],
        ))
        
        self.register(FunctionMetadata(
            name="send_todays_lesson",
            description="Send today's scheduled lesson with full text. Use when user asks for 'today's lesson', 'the text', 'all the text', 'full text', or 'entire lesson'.",
            parameters=[
                ParameterSchema(
                    name="lesson_id",
                    description="Lesson ID (optional, defaults to today's)",
                    type=ParameterType.INTEGER,
                    required=False,
                    examples=[1, 42, 365],
                ),
            ],
            contexts=["general_chat", "morning_lesson_confirmation"],
        ))
        
        # Profile functions
        self.register(FunctionMetadata(
            name="set_timezone",
            description="Set user's timezone",
            parameters=[
                ParameterSchema(
                    name="timezone",
                    description="Timezone (e.g. Europe/Oslo)",
                    type=ParameterType.TIMEZONE,
                    required=True,
                    examples=["Europe/Oslo", "America/New_York", "Asia/Tokyo"],
                ),
            ],
            contexts=["general_chat", "onboarding"],
        ))
        
        self.register(FunctionMetadata(
            name="set_language",
            description="Set user's preferred language",
            parameters=[
                ParameterSchema(
                    name="language",
                    description="ISO 639-1 language code",
                    type=ParameterType.STRING,
                    required=True,
                    examples=["en", "no", "es", "de"],
                ),
            ],
            contexts=["general_chat", "onboarding", "onboarding_name"],
        ))
        
        self.register(FunctionMetadata(
            name="set_preferred_time",
            description="Set preferred lesson time",
            parameters=[
                ParameterSchema(
                    name="time",
                    description="Preferred time in HH:MM format",
                    type=ParameterType.TIME,
                    required=True,
                    examples=["09:00", "20:00"],
                ),
            ],
            contexts=["general_chat", "onboarding", "schedule_setup"],
        ))
        
        self.register(FunctionMetadata(
            name="update_profile",
            description="Update user profile information",
            parameters=[
                ParameterSchema(
                    name="key",
                    description="Profile field to update",
                    type=ParameterType.STRING,
                    required=True,
                    examples=["name", "email", "background"],
                ),
                ParameterSchema(
                    name="value",
                    description="New value for the field",
                    type=ParameterType.STRING,
                    required=True,
                ),
            ],
            contexts=["general_chat", "onboarding", "onboarding_name"],
        ))
                
        # Confirmation functions
        self.register(FunctionMetadata(
            name="confirm_yes",
            description="User confirmed or completed something",
            parameters=[
                ParameterSchema(
                    name="context",
                    description="Context string",
                    type=ParameterType.STRING,
                    required=False,
                    examples=["lesson_repeat", "schedule_created"],
                ),
            ],
            contexts=["general_chat", "lesson_review", "onboarding", "onboarding_name", "onboarding_consent"],
        ))
        
        self.register(FunctionMetadata(
            name="confirm_no",
            description="User declined or has not completed something",
            parameters=[
                ParameterSchema(
                    name="context",
                    description="Context string",
                    type=ParameterType.STRING,
                    required=False,
                    examples=["not_completed", "needs_more_time"],
                ),
            ],
            contexts=["general_chat", "lesson_review", "onboarding", "onboarding_name", "onboarding_consent"],
        ))
        
        # Memory extraction function
        self.register(FunctionMetadata(
            name="extract_memory",
            description="Extract and store a memory from user conversation. Use when the user shares personal information, preferences, or facts to remember.",
            parameters=[
                ParameterSchema(
                    name="key",
                    description="Memory key (e.g., 'first_name', 'timezone', 'current_lesson')",
                    type=ParameterType.STRING,
                    required=True,
                    examples=["first_name", "timezone", "current_lesson", "preferred_lesson_time", "learning_goal"],
                ),
                ParameterSchema(
                    name="value",
                    description="The value to store",
                    type=ParameterType.STRING,
                    required=True,
                    examples=["Sarah", "Europe/Oslo", "25", "09:00", "spiritual growth"],
                ),
                ParameterSchema(
                    name="ttl_hours",
                    description="Time-to-live in hours (optional)",
                    type=ParameterType.INTEGER,
                    required=False,
                    examples=[24, 168, 720],
                ),
            ],
            examples=[
                {"key": "first_name", "value": "Sarah"},
                {"key": "timezone", "value": "Asia/Tokyo"},
                {"key": "current_lesson", "value": "25"},
            ],
            contexts=["general_chat", "onboarding", "onboarding_name", "onboarding_consent", "schedule_setup", "lesson_review", "morning_lesson_confirmation"],
        ))
        
# Lesson state function - dedicated function for setting current lesson
        self.register(FunctionMetadata(
            name="set_current_lesson",
            description="Set the user's current ACIM lesson number. Use when user says 'I am on lesson X'.",
            parameters=[
                ParameterSchema(
                    name="lesson_number",
                    description="Lesson number (1-365)",
                    type=ParameterType.INTEGER,
                    required=True,
                    examples=[1, 28, 29, 100],
                ),
            ],
            examples=[
                {"lesson_number": 29},
            ],
            contexts=["general_chat", "onboarding", "lesson_review"],
        ))

        # Memory deletion function - AI callable version to forget memory
        self.register(FunctionMetadata(
            name="forget_memories",
            description="Forget (archive) user memories matching a semantic description. Use when user wants to remove personal memories.",
            parameters=[
                ParameterSchema(
                    name="query_text",
                    description="Description of memories to forget/search for (e.g. 'my grandfather', 'test memory')",
                    type=ParameterType.STRING,
                    required=True,
                    examples=["my childhood", "test data", "grandmother story"],
                ),
            ],
            examples=[
                {"query_text": "test memories"},
                {"query_text": "personal family information"},
            ],
            contexts=["general_chat", "rag"],
        ))
    
    def register(self, function: FunctionMetadata):
        """Register a function."""
        self._functions[function.name] = function
        logger.debug(f"Registered function: {function.name}")
    
    def get(self, name: str) -> Optional[FunctionMetadata]:
        """Get a function by name."""
        return self._functions.get(name)
    
    def list_all(self) -> List[FunctionMetadata]:
        """List all registered functions."""
        return list(self._functions.values())
    
    def list_for_context(self, context: str) -> List[FunctionMetadata]:
        """List functions available in a specific context."""
        return [
            f for f in self._functions.values()
            if context in f.contexts or "general_chat" in f.contexts
        ]
    
    def validate_call(self, name: str, parameters: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate a function call."""
        function = self.get(name)
        if not function:
            return False, [f"Unknown function: {name}"]
        
        return function.validate_parameters(parameters)
    
    def is_valid_function(self, name: str) -> bool:
        """Check if a function name is valid."""
        return name in self._functions


# Global registry instance
_registry: Optional[FunctionRegistry] = None


def get_function_registry() -> FunctionRegistry:
    """Get the global function registry."""
    global _registry
    if _registry is None:
        _registry = FunctionRegistry()
    return _registry


def reset_registry():
    """Reset the global registry (useful for testing)."""
    global _registry
    _registry = None

