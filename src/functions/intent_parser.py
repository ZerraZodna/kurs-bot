"""
Intent Parser for Function Calling.

Parses and validates JSON responses from the AI, extracting function calls
and handling malformed responses gracefully.
"""

import json
import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from .registry import FunctionRegistry, get_function_registry

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing an AI response."""
    success: bool
    response_text: str
    functions: List[Dict[str, Any]]
    errors: List[str]
    raw_response: str
    is_fallback: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "response_text": self.response_text,
            "functions": self.functions,
            "errors": self.errors,
            "is_fallback": self.is_fallback,
        }


class IntentParser:
    """Parse AI responses and extract function calls."""
    
    def __init__(self, registry: Optional[FunctionRegistry] = None):
        self.registry = registry or get_function_registry()
    
    def parse(self, response_text: str) -> ParseResult:
        """
        Parse an AI response and extract function calls.
        
        Args:
            response_text: Raw text response from AI
            
        Returns:
            ParseResult with extracted functions or error info
        """
        logger.debug(f"Parsing AI response: {response_text[:200]}...")
        print(f"[DEBUG] Parsing AI response: {response_text[:200]}...")
        
        if not response_text or not response_text.strip():
            return ParseResult(
                success=False,
                response_text="",
                functions=[],
                errors=["Empty response"],
                raw_response=response_text,
            )
        
        # Try to extract and parse JSON
        json_str = self._extract_json(response_text)
        
        if not json_str:
            logger.debug("No JSON found in response, treating as natural language")
            # No JSON found - treat as natural language only
            return self._create_fallback_result(response_text)
        
        logger.debug(f"Extracted JSON: {json_str[:200]}...")
        
        try:
            data = json.loads(json_str)
            return self._validate_and_extract(data, response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            # Try to fix common JSON issues
            fixed_json = self._attempt_json_repair(json_str)
            if fixed_json:
                try:
                    data = json.loads(fixed_json)
                    return self._validate_and_extract(data, response_text)
                except json.JSONDecodeError:
                    pass
            
            # Fall back to treating as natural language
            return self._create_fallback_result(response_text, [f"JSON parse error: {e}"])
        except Exception as e:
            logger.error(f"Unexpected parse error: {e}")
            return self._create_fallback_result(response_text, [f"Parse error: {e}"])
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text, handling markdown code blocks."""
        text = text.strip()
        
        # Try to find JSON in markdown code blocks
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",  # ```json ... ```
            r"```\s*([\s\S]*?)\s*```",       # ``` ... ```
            r"\{[\s\S]*\}",                  # Raw JSON object
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Check if it looks like valid JSON
                if match.strip().startswith("{") or match.strip().startswith("["):
                    return match.strip()
        
        # If no code blocks, check if entire text is JSON
        if text.startswith("{") and text.endswith("}"):
            return text
        
        return None
    
    def _attempt_json_repair(self, json_str: str) -> Optional[str]:
        """Attempt to fix common JSON formatting issues."""
        # Try adding missing quotes around keys
        try:
            # Replace single quotes with double quotes
            fixed = json_str.replace("'", '"')
            
            # Try to parse
            json.loads(fixed)
            return fixed
        except:
            pass
        
        # Try to extract just the object part
        try:
            start = json_str.find("{")
            end = json_str.rfind("}")
            if start != -1 and end != -1:
                return json_str[start:end+1]
        except:
            pass
        
        return None
    
    def _validate_and_extract(self, data: Dict[str, Any], raw_response: str) -> ParseResult:
        """Validate parsed JSON and extract function calls."""
        errors = []
        
        logger.debug(f"Validating and extracting from data: {data}")
        
        # Check for required fields
        if "response" not in data:
            errors.append("Missing 'response' field")
            response_text = ""
        else:
            response_text = str(data["response"]) if data["response"] is not None else ""
        
        # Extract functions
        functions = []
        if "functions" in data:
            if not isinstance(data["functions"], list):
                errors.append("'functions' must be an array")
            else:
                logger.debug(f"Found {len(data['functions'])} functions in response")
                print(f"[DEBUG] Found {len(data['functions'])} functions in response")
                for i, func in enumerate(data["functions"]):
                    func_errors = self._validate_function_call(func, i)
                    if func_errors:
                        errors.extend(func_errors)
                    else:
                        functions.append(func)
                        logger.debug(f"Extracted function: {func.get('name')} with params: {func.get('parameters')}")
                        print(f"[DEBUG] Extracted function: {func.get('name')} with params: {func.get('parameters')}")
        # Also support legacy "intent" field for backward compatibility
        elif "intent" in data:
            intent = data["intent"]
            if isinstance(intent, dict):
                func_call = {
                    "name": intent.get("action_type") or intent.get("name"),
                    "parameters": intent.get("parameters") or {},
                }
                func_errors = self._validate_function_call(func_call, 0)
                if func_errors:
                    errors.extend(func_errors)
                else:
                    functions.append(func_call)
        
        success = len(errors) == 0 or len(functions) > 0
        
        logger.debug(f"Parse result: success={success}, functions={len(functions)}, errors={errors}")
        print(f"[DEBUG] Parse result: success={success}, functions={len(functions)}, errors={errors}")
        if functions:
            print(f"[DEBUG] Functions returned to agent: {functions}")
        
        return ParseResult(
            success=success,
            response_text=response_text,
            functions=functions,
            errors=errors,
            raw_response=raw_response,
        )
    
    def _validate_function_call(self, func: Any, index: int) -> List[str]:
        """Validate a single function call."""
        errors = []
        
        if not isinstance(func, dict):
            return [f"Function {index} must be an object"]
        
        # Check required fields
        if "name" not in func:
            errors.append(f"Function {index} missing 'name'")
        else:
            name = func["name"]
            if not self.registry.is_valid_function(name):
                errors.append(f"Unknown function: {name}")
        
        # Parameters is optional - default to empty dict if not provided
        parameters = func.get("parameters", {})
        if not isinstance(parameters, dict):
            errors.append(f"Function {index} 'parameters' must be an object")
        else:
            # Validate parameters against schema
            name = func.get("name")
            if name:
                is_valid, param_errors = self.registry.validate_call(
                    name, parameters
                )
                if not is_valid:
                    errors.extend([f"Function {index}: {e}" for e in param_errors])
        
        return errors
    
    def _create_fallback_result(self, response_text: str, errors: Optional[List[str]] = None) -> ParseResult:
        """Create a fallback result treating response as natural language."""
        return ParseResult(
            success=True,  # Still success - we have text to show
            response_text=response_text.strip(),
            functions=[],
            errors=errors or [],
            raw_response=response_text,
            is_fallback=True,
        )
    
    def parse_batch(self, responses: List[str]) -> List[ParseResult]:
        """Parse multiple responses."""
        return [self.parse(r) for r in responses]
    
    def extract_single_function(self, response_text: str, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract a specific function call from response.
        
        Useful for checking if a specific action was requested.
        """
        result = self.parse(response_text)
        if not result.success:
            return None
        
        for func in result.functions:
            if func.get("name") == function_name:
                return func
        
        return None
    
    def has_function(self, response_text: str, function_name: str) -> bool:
        """Check if response contains a specific function call."""
        return self.extract_single_function(response_text, function_name) is not None


# Global instance
_parser: Optional[IntentParser] = None


def get_intent_parser(registry: Optional[FunctionRegistry] = None) -> IntentParser:
    """Get the global intent parser instance."""
    global _parser
    if _parser is None:
        _parser = IntentParser(registry)
    return _parser


def reset_parser():
    """Reset the global instance (useful for testing)."""
    global _parser
    _parser = None


def quick_parse(response_text: str) -> ParseResult:
    """Quick parse function for convenience."""
    parser = get_intent_parser()
    return parser.parse(response_text)
