"""
Function Executor for ACIM Course Bot.

Executes function calls from the AI, handling sequential execution,
error handling, and result collection.
"""

import logging
from dataclasses import dataclass, field
from src.core.timezone import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar

from src.models.database import Session as DBSession
from src.models.schedule import Lesson

from .handlers import LessonProfileHandler, MemoryHandler, ScheduleHandler
from .parameters import ParameterValidator
from .registry import FunctionRegistry, get_function_registry

logger = logging.getLogger(__name__)


T = TypeVar("T")


class HasExecute(Protocol):
    async def __call__(self, *args: Any, **kwargs: Any) -> Dict[str, Any]: ...


@dataclass
class ExecutionResult:
    """Result of executing a single function."""

    function_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "function_name": self.function_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class BatchExecutionResult:
    """Result of executing multiple functions."""

    results: List[ExecutionResult] = field(default_factory=list)
    all_succeeded: bool = True
    total_execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "results": [r.to_dict() for r in self.results],
            "all_succeeded": self.all_succeeded,
            "total_execution_time_ms": self.total_execution_time_ms,
        }

    def get_successful_results(self) -> List[ExecutionResult]:
        """Get only successful results."""
        return [r for r in self.results if r.success]

    def get_failed_results(self) -> List[ExecutionResult]:
        """Get only failed results."""
        return [r for r in self.results if not r.success]


class FunctionExecutor:
    """Executes function calls with error handling and result collection."""

    def __init__(self, registry: Optional[FunctionRegistry] = None):
        self.registry = registry or get_function_registry()
        self._handlers: Dict[str, Callable] = {}
        self.schedule_handler = ScheduleHandler(self)
        self.lesson_profile_handler = LessonProfileHandler(self)
        self.memory_handler = MemoryHandler(self)
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default function handlers."""
        # Scheduling handlers
        self._handlers["create_schedule"] = self.schedule_handler.handle
        self._handlers["update_schedule"] = self.schedule_handler.handle
        self._handlers["delete_schedule"] = self.schedule_handler.handle
        self._handlers["query_schedule"] = self.schedule_handler.handle
        self._handlers["create_one_time_reminder"] = self.schedule_handler.handle
        self._handlers["delete_one_time_reminder"] = self.schedule_handler.handle
        self._handlers["delete_all_one_time_reminders"] = self.schedule_handler.handle
        self._handlers["delete_all_daily_reminders"] = self.schedule_handler.handle
        self._handlers["delete_all_reminders"] = self.schedule_handler.handle

        # Lesson/profile handlers
        self._handlers["send_lesson"] = self.lesson_profile_handler.handle
        self._handlers["send_todays_lesson"] = self.lesson_profile_handler.handle
        self._handlers["set_current_lesson"] = self.lesson_profile_handler.handle
        self._handlers["set_timezone"] = self.lesson_profile_handler.handle
        self._handlers["set_language"] = self.lesson_profile_handler.handle
        self._handlers["set_preferred_time"] = self.lesson_profile_handler.handle
        self._handlers["update_profile"] = self.lesson_profile_handler.handle

        # Memory/confirm handlers
        self._handlers["confirm_yes"] = self.memory_handler.handle
        self._handlers["confirm_no"] = self.memory_handler.handle
        self._handlers["extract_memory"] = self.memory_handler.handle
        self._handlers["forget_memories"] = self.memory_handler.handle

    def register_handler(self, function_name: str, handler: Callable) -> None:
        """Register a custom handler for a function."""
        self._handlers[function_name] = handler
        logger.debug(f"Registered handler for function: {function_name}")

    # ============== DRY Helper Methods ==============

    def _ok_response(self, **kwargs: Any) -> Dict[str, Any]:
        """Build a success response."""
        return {"ok": True, **kwargs}

    def _error_response(self, error: str, **kwargs: Any) -> Dict[str, Any]:
        """Build an error response."""
        return {"ok": False, "error": error, **kwargs}

    def _validate_time(self, time_str: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Validate and normalize time string. Returns (is_valid, normalized, error)."""
        return ParameterValidator.validate_time(time_str)

    def _validate_timezone(self, tz_str: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Validate and normalize timezone string. Returns (is_valid, normalized, error)."""
        return ParameterValidator.validate_timezone(tz_str)

    def _validate_language(self, lang_str: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Validate and normalize language string. Returns (is_valid, normalized, error)."""
        return ParameterValidator.validate_language(lang_str)

    def _validate_datetime(self, dt_str: str) -> tuple[bool, Optional[datetime], Optional[str]]:
        """Validate and normalize datetime string. Returns (is_valid, datetime_obj, error)."""
        return ParameterValidator.validate_datetime(dt_str)

    def _get_lesson_by_id(self, lesson_id: int, session: DBSession) -> Optional[Lesson]:
        """Get lesson by ID from database."""
        return session.query(Lesson).filter_by(lesson_id=lesson_id).first()

    def _get_memory_category_for_key(self, key: str) -> str:
        """Infer memory category from key name."""
        from src.memories.constants import MemoryCategory, MemoryKey

        # Safe attribute check for mypy
        if hasattr(MemoryKey, "PROFILE_KEYS") and key in getattr(MemoryKey, "PROFILE_KEYS", []):
            return MemoryCategory.PROFILE.value
        elif hasattr(MemoryKey, "PROGRESS_KEYS") and key in getattr(MemoryKey, "PROGRESS_KEYS", []):
            return MemoryCategory.PROGRESS.value
        else:
            return MemoryCategory.CONVERSATION.value

    async def safe_db_wrapper(
        self, session: Optional[DBSession], func: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        try:
            return await func(*args, session=session, **kwargs)
        except Exception as e:
            logger.exception("safe_db_wrapper error")
            return self._error_response(f"DB operation failed: {str(e)}")

    async def safe_memory_wrapper(
        self, memory_manager: Optional[Any], func: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        try:
            return await func(*args, memory_manager=memory_manager, **kwargs)
        except Exception as e:
            logger.exception("safe_memory_wrapper error")
            return self._error_response(f"Memory operation failed: {str(e)}")

    async def execute_all(
        self,
        functions: List[Dict[str, Any]],
        context: Dict[str, Any],
        continue_on_error: bool = True,
    ) -> BatchExecutionResult:
        """
        Execute all function calls sequentially.

        Args:
            functions: List of function calls with 'name' and 'parameters'
            context: Execution context (user_id, session, memory_manager, etc.)
            continue_on_error: Whether to continue executing after an error

        Returns:
            BatchExecutionResult with all execution results
        """
        import time

        batch_result = BatchExecutionResult()
        start_time = time.time()

        for func_call in functions:
            function_name = func_call.get("name")
            parameters = func_call.get("parameters", {})

            logger.info(f"[executor] Processing function call: name='{function_name}'")

            # Validate function exists
            if not self.registry.is_valid_function(function_name):
                result = ExecutionResult(
                    function_name=function_name or "unknown",
                    success=False,
                    error=f"Unknown function: {function_name}",
                )
                batch_result.results.append(result)
                if not continue_on_error:
                    break
                continue

            # Validate parameters
            is_valid, errors = self.registry.validate_call(function_name, parameters)
            if not is_valid:
                result = ExecutionResult(
                    function_name=function_name,
                    success=False,
                    error=f"Parameter validation failed: {', '.join(errors)}",
                )
                batch_result.results.append(result)
                if not continue_on_error:
                    break
                continue

            exec_start = time.time()
            handler = self._handlers.get(function_name)

            if handler is None:
                logger.warning(f"No handler for '{function_name}'")
                result = ExecutionResult(
                    function_name=function_name,
                    success=False,
                    error=f"No handler registered for '{function_name}'",
                )
                batch_result.results.append(result)
                continue

            exec_time = (time.time() - exec_start) * 1000
            try:
                if handler.__name__ == "handle":
                    handler_result = await handler(function_name, parameters, context)
                else:
                    handler_result = await handler(parameters, context)

                from typing import cast

                result = ExecutionResult(
                    function_name=function_name,
                    success=True,
                    result=cast(Dict[str, Any], handler_result),
                    execution_time_ms=exec_time,
                )
                logger.info(f"Executed {function_name} in {exec_time:.2f}ms")
            except Exception as e:
                logger.exception(f"Handler error {function_name}")
                result = ExecutionResult(
                    function_name=function_name,
                    success=False,
                    error=str(e),
                    execution_time_ms=exec_time,
                )

            batch_result.results.append(result)
            if not result.success and not continue_on_error:
                break

        # Calculate batch results
        batch_result.total_execution_time_ms = (time.time() - start_time) * 1000
        batch_result.all_succeeded = all(r.success for r in batch_result.results)

        logger.info(
            f"Batch: {len([r for r in batch_result.results if r.success])} success, total {batch_result.total_execution_time_ms:.2f}ms"
        )

        return batch_result

    async def execute_single(
        self,
        function_name: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute single function call."""
        if not self.registry.is_valid_function(function_name):
            return ExecutionResult(
                function_name=function_name, success=False, error=f"Unknown function: {function_name}"
            )

        is_valid, errors = self.registry.validate_call(function_name, parameters)
        if not is_valid:
            return ExecutionResult(
                function_name=function_name, success=False, error=f"Validation failed: {', '.join(errors)}"
            )

        handler = self._handlers.get(function_name)
        if handler is None:
            return ExecutionResult(
                function_name=function_name, success=False, error=f"No handler for '{function_name}'"
            )

        import time

        start_time = time.time()
        try:
            if handler.__name__ == "handle":
                result = await handler(function_name, parameters, context)
            else:
                result = await handler(parameters, context)
        except Exception as e:
            logger.exception(f"Handler error {function_name}")
            exec_time = (time.time() - start_time) * 1000
            return ExecutionResult(
                function_name=function_name, success=False, error=str(e), execution_time_ms=exec_time
            )

        exec_time = (time.time() - start_time) * 1000
        return ExecutionResult(function_name=function_name, success=True, result=result, execution_time_ms=exec_time)


# Global instance
_executor: Optional[FunctionExecutor] = None


def get_function_executor(registry: Optional[FunctionRegistry] = None) -> FunctionExecutor:
    """Get global executor instance."""
    global _executor
    if _executor is None:
        _executor = FunctionExecutor(registry)
    return _executor


def reset_executor() -> None:
    """Reset for testing."""
    global _executor
    _executor = None
