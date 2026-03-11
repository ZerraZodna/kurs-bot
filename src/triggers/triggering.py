import json
import logging
from typing import Optional, Dict, Any

from src.functions.intent_parser import get_intent_parser
from src.functions.executor import get_function_executor, BatchExecutionResult
from src.config import settings

logger = logging.getLogger(__name__)


async def handle_triggers(
    response: str,
    original_text: str,
    session,
    memory_manager,
    user_id: int,
    original_text_embedding=None,  # Kept for backward compatibility but no longer used
) -> Dict[str, Any]:
    """Run trigger dispatching for a dialogue turn.

    This will parse the structured intent from the assistant response,
    execute any functions, and dispatch actions via the trigger system.
    """
    diagnostics: Dict[str, Any] = {
        "structured_intent_used": False,
        "dispatched_actions": [],
    }

    try:
        # Guard: if response is None, skip processing
        if response is None:
            logger.warning("Assistant response is None; skipping trigger handling")
            return diagnostics

        logger.debug(f"Handling triggers for response (FULL): {response}")
        
        # Parse the response using IntentParser
        parser = get_intent_parser()
        parse_result = parser.parse(response)
        
        logger.debug(f"Parse result: success={parse_result.success}, functions={len(parse_result.functions)}, is_fallback={parse_result.is_fallback}")
        
        # Track dispatched action_types per dialogue turn to avoid duplicate handling
        dispatched_actions: set = set()
        
        # If we have a text response, record it
        if parse_result.response_text:
            diagnostics["response_text"] = parse_result.response_text
        
        # If we have functions to execute, process them
        if parse_result.functions:
            logger.info(f"Processing {len(parse_result.functions)} functions for user={user_id}")
            diagnostics["structured_intent_used"] = True
            
            # Log each function being processed
            for func in parse_result.functions:
                logger.debug(f"Function to execute: {func.get('name')} with params: {func.get('parameters')}")
            
            # Execute all functions
            executor = get_function_executor()
            execution_context = {
                "user_id": user_id,
                "session": session,
                "memory_manager": memory_manager,
                "original_text": original_text,
            }
            
            execution_result = await executor.execute_all(
                parse_result.functions,
                execution_context,
                continue_on_error=True
            )
            
            # Record execution results in diagnostics
            diagnostics["function_execution"] = {
                "all_succeeded": execution_result.all_succeeded,
                "total_execution_time_ms": execution_result.total_execution_time_ms,
                "results": [r.to_dict() for r in execution_result.results]
            }
            
            # Store the full execution result for response building
            diagnostics["execution_result"] = execution_result
            
            # Record which functions were successfully executed
            for result in execution_result.results:
                if result.success:
                    dispatched_actions.add(result.function_name)
                    
            diagnostics["dispatched_actions"] = sorted(dispatched_actions)
            logger.info(f"Dispatched actions: {sorted(dispatched_actions)}")
        
        # If no functions were found but we have JSON-like content, log it
        elif "{" in response and "}" in response:
            logger.debug(f"Response contains JSON-like content but no functions were parsed: {response[:100]}...")
            logger.debug(f"Response text extracted: {parse_result.response_text[:100]}...")
            logger.debug(f"Response contains JSON-like content but no functions were parsed")
            if parse_result.errors:
                logger.warning(f"Parse errors: {parse_result.errors}")
                diagnostics["parse_errors"] = parse_result.errors

    except Exception as e:
        logger.warning(f"Function handling failed: {e}")
        diagnostics["error"] = str(e)

    return diagnostics
