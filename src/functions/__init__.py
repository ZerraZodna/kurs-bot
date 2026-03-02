"""
Function Calling Infrastructure for ACIM Course Bot.

This module provides the infrastructure for function calling with the LLM,
replacing the previous embedding-based trigger matching system.

Components:
- FunctionRegistry: Defines available functions and their metadata
- FunctionDefinitions: Generates prompt text for function descriptions
- IntentParser: Parses and validates JSON responses from the LLM
- FunctionExecutor: Executes function calls
- ResponseBuilder: Builds responses combining text and function results

Version: 1.0.0
"""

from .registry import FunctionRegistry, FunctionMetadata, ParameterSchema
from .definitions import FunctionDefinitions
from .intent_parser import IntentParser, ParseResult
from .executor import FunctionExecutor
from .response_builder import ResponseBuilder

__all__ = [
    "FunctionRegistry",
    "FunctionMetadata", 
    "ParameterSchema",
    "FunctionDefinitions",
    "IntentParser",
    "ParseResult",
    "FunctionExecutor",
    "ResponseBuilder",
]

__version__ = "1.0.0"
