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

from .definitions import FunctionDefinitions
from .executor import FunctionExecutor, get_function_executor
from .intent_parser import IntentParser, ParseResult, get_intent_parser
from .registry import FunctionMetadata, FunctionRegistry, ParameterSchema
from .response_builder import ResponseBuilder, get_response_builder

__all__ = [
    "FunctionRegistry",
    "FunctionMetadata", 
    "ParameterSchema",
    "FunctionDefinitions",
    "IntentParser",
    "ParseResult",
    "get_intent_parser",
    "FunctionExecutor",
    "get_function_executor",
    "ResponseBuilder",
    "get_response_builder",
]

__version__ = "1.0.0"
