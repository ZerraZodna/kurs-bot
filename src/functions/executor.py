"""
Function Executor for ACIM Course Bot.

Executes function calls from the AI, handling sequential execution,
error handling, and result collection.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .registry import FunctionRegistry, get_function_registry
from .parameters import ParameterValidator
from src.memories.constants import MemoryCategory, MemoryKey
from src.models.schedule import Lesson
from src.lessons.state import compute_current_lesson_state

logger = logging.getLogger(__name__)


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
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default function handlers."""
        # Scheduling handlers
        self._handlers["create_schedule"] = self._handle_create_schedule
        self._handlers["update_schedule"] = self._handle_update_schedule
        self._handlers["delete_schedule"] = self._handle_delete_schedule
        self._handlers["query_schedule"] = self._handle_query_schedule
        self._handlers["create_one_time_reminder"] = self._handle_create_one_time_reminder
        self._handlers["delete_one_time_reminder"] = self._handle_delete_one_time_reminder
        self._handlers["delete_all_one_time_reminders"] = self._handle_delete_all_one_time_reminders
        self._handlers["delete_all_daily_reminders"] = self._handle_delete_all_daily_reminders
        self._handlers["delete_all_reminders"] = self._handle_delete_all_reminders
        
        # Lesson handlers
        self._handlers["send_lesson"] = self._handle_send_lesson
        self._handlers["send_todays_lesson"] = self._handle_send_todays_lesson
        self._handlers["set_current_lesson"] = self._handle_set_current_lesson
        
        # Profile handlers
        self._handlers["set_timezone"] = self._handle_set_timezone
        self._handlers["set_language"] = self._handle_set_language
        self._handlers["set_preferred_time"] = self._handle_set_preferred_time
        self._handlers["update_profile"] = self._handle_update_profile
                
        # Confirmation handlers
        self._handlers["confirm_yes"] = self._handle_confirm_yes
        self._handlers["confirm_no"] = self._handle_confirm_no
        
        # Memory extraction handler
        self._handlers["extract_memory"] = self._handle_extract_memory
        
        # Memory deletion handler (AI version of forget memory)
        self._handlers["forget_memories"] = self._handle_forget_memories

    
    def register_handler(self, function_name: str, handler: Callable):
        """Register a custom handler for a function."""
        self._handlers[function_name] = handler
        logger.debug(f"Registered handler for function: {function_name}")
    
    # ============== DRY Helper Methods ==============
    
    def _ok_response(self, **kwargs) -> Dict[str, Any]:
        """Build a success response."""
        return {"ok": True, **kwargs}
    
    def _error_response(self, error: str, **kwargs) -> Dict[str, Any]:
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
    
    def _get_lesson_by_id(self, lesson_id: int, session) -> Optional[Lesson]:
        """Get lesson by ID from database."""
        return session.query(Lesson).filter_by(lesson_id=lesson_id).first()
    
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
            
            # Execute the function
            try:
                exec_start = time.time()
                handler = self._handlers.get(function_name)
                
                if handler is None:
                    result = ExecutionResult(
                        function_name=function_name,
                        success=False,
                        error=f"No handler registered for function: {function_name}",
                    )
                else:
                    # Call the handler
                    handler_result = await handler(parameters, context)
                    exec_time = (time.time() - exec_start) * 1000
                    
                    result = ExecutionResult(
                        function_name=function_name,
                        success=True,
                        result=handler_result,
                        execution_time_ms=exec_time,
                    )
                    logger.info(f"Executed {function_name} in {exec_time:.2f}ms")
                
                batch_result.results.append(result)
                
                if not result.success and not continue_on_error:
                    break
                    
            except Exception as e:
                exec_time = (time.time() - exec_start) * 1000
                logger.exception(f"Error executing function {function_name}")
                
                result = ExecutionResult(
                    function_name=function_name,
                    success=False,
                    error=str(e),
                    execution_time_ms=exec_time,
                )
                batch_result.results.append(result)
                
                if not continue_on_error:
                    break
        
        # Calculate batch results
        batch_result.total_execution_time_ms = (time.time() - start_time) * 1000
        batch_result.all_succeeded = all(r.success for r in batch_result.results)
        
        logger.info(
            f"Batch execution completed: {len(batch_result.get_successful_results())} succeeded, "
            f"{len(batch_result.get_failed_results())} failed, "
            f"total time: {batch_result.total_execution_time_ms:.2f}ms"
        )
        
        return batch_result
    
    async def execute_single(
        self,
        function_name: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """
        Execute a single function call.
        
        Args:
            function_name: Name of the function to execute
            parameters: Function parameters
            context: Execution context
            
        Returns:
            ExecutionResult
        """
        # Validate function exists
        if not self.registry.is_valid_function(function_name):
            return ExecutionResult(
                function_name=function_name,
                success=False,
                error=f"Unknown function: {function_name}",
            )
        
        # Validate parameters
        is_valid, errors = self.registry.validate_call(function_name, parameters)
        if not is_valid:
            return ExecutionResult(
                function_name=function_name,
                success=False,
                error=f"Parameter validation failed: {', '.join(errors)}",
            )
        
        # Execute
        try:
            import time
            start_time = time.time()
            
            handler = self._handlers.get(function_name)
            if handler is None:
                return ExecutionResult(
                    function_name=function_name,
                    success=False,
                    error=f"No handler registered for function: {function_name}",
                )
            
            result = await handler(parameters, context)
            exec_time = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                function_name=function_name,
                success=True,
                result=result,
                execution_time_ms=exec_time,
            )
            
        except Exception as e:
            logger.exception(f"Error executing function {function_name}")
            return ExecutionResult(
                function_name=function_name,
                success=False,
                error=str(e),
            )
    
    # ============== Handler Methods ==============
    
    async def _handle_create_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_schedule function."""
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        time = params.get("time")
        message = params.get("message", "Time for your ACIM lesson")
        lesson_id = params.get("lesson_id")
        
        # Validate time format using DRY helper
        is_valid, normalized_time, error = self._validate_time(time)
        if not is_valid:
            return self._error_response(error)
        
        try:
            schedule = scheduler_api.create_daily_schedule(
                user_id=user_id,
                lesson_id=lesson_id,
                time_str=normalized_time,
                session=context.get("session"),
            )
            return self._ok_response(
                schedule_id=schedule.schedule_id,
                time=normalized_time,
                message=message,
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_update_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_schedule function."""
        from src.scheduler import api as scheduler_api
        
        schedule_id = params.get("schedule_id")
        time = params.get("time")
        
        # Validate time format using DRY helper
        is_valid, normalized_time, error = self._validate_time(time)
        if not is_valid:
            return self._error_response(error)
        
        try:
            updated = scheduler_api.update_daily_schedule(
                schedule_id=schedule_id,
                time_str=normalized_time,
                session=context.get("session"),
            )
            if updated:
                return self._ok_response(
                    schedule_id=updated.schedule_id,
                    time=normalized_time,
                )
            return self._error_response("Schedule not found or update failed")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_delete_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_schedule function."""
        from src.scheduler import api as scheduler_api
        
        schedule_id = params.get("schedule_id")
        
        try:
            result = scheduler_api.deactivate_schedule(
                schedule_id=schedule_id,
                session=context.get("session"),
            )
            if result:
                return self._ok_response(schedule_id=schedule_id)
            return self._error_response("Schedule not found or already inactive")
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_query_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query_schedule function."""
        from src.scheduler import api as scheduler_api
        from src.scheduler.domain import is_one_time_schedule_type
        from src.scheduler.memory_helpers import get_schedule_message
        from src.core.timezone import get_user_timezone_from_db, format_dt_in_timezone
        
        user_id = context.get("user_id")
        session = context.get("session")
        memory_manager = context.get("memory_manager")
        
        # Get user's timezone for converting times to local display
        tz_name = get_user_timezone_from_db(session, user_id) if session else "UTC"
        
        try:
            schedules = scheduler_api.get_user_schedules(
                user_id=user_id,
                active_only=True,
                session=session,
            )
            
            schedule_list = []
            for s in schedules:
                # Convert next_send_time to user's local timezone for display
                local_time = None
                if s.next_send_time:
                    local_dt, _ = format_dt_in_timezone(s.next_send_time, tz_name)
                    local_time = local_dt.isoformat()
                
                schedule_data = {
                    "schedule_id": s.schedule_id,
                    "schedule_type": s.schedule_type,
                    "cron_expression": s.cron_expression,
                    "next_send_time": local_time,  # Return local time, not UTC
                    "is_active": s.is_active,
                }
                
                # For one-time reminders, fetch the message from memory
                if is_one_time_schedule_type(s.schedule_type) and memory_manager:
                    message = get_schedule_message(memory_manager, user_id, s.schedule_id)
                    if message:
                        schedule_data["message"] = message
                
                schedule_list.append(schedule_data)
            
            return self._ok_response(
                schedules=schedule_list,
                timezone=tz_name,  # Include timezone info for debugging
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_create_one_time_reminder(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_one_time_reminder function."""
        from src.scheduler import api as scheduler_api
        from src.core.timezone import to_utc
        
        user_id = context.get("user_id")
        run_at = params.get("run_at")
        message = params.get("message", "Reminder")
        
        # Validate datetime using DRY helper
        is_valid, dt_obj, error = self._validate_datetime(run_at)
        if not is_valid:
            return self._error_response(error)
        
        try:
            # Convert to UTC for storage
            run_at_utc = to_utc(dt_obj)
            schedule = scheduler_api.create_one_time_schedule(
                user_id=user_id,
                run_at=run_at_utc,
                message=message,
                session=context.get("session"),
            )
            return self._ok_response(
                schedule_id=schedule.schedule_id,
                run_at=run_at_utc.isoformat(),  # Return UTC time for proper display
                message=message,
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_delete_one_time_reminder(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_one_time_reminder function."""
        from src.scheduler import manager as schedule_manager
        from src.scheduler.domain import is_one_time_schedule_type
        
        user_id = context.get("user_id")
        schedule_id = params.get("schedule_id")
        session = context.get("session")
        
        try:
            # Get the schedule to verify it exists and belongs to the user
            from src.models.database import Schedule
            schedule = session.query(Schedule).filter_by(
                schedule_id=schedule_id, 
                user_id=user_id
            ).first()
            
            if not schedule:
                return self._error_response("Schedule not found")
            
            # Verify it's a one-time reminder
            if not is_one_time_schedule_type(schedule.schedule_type):
                return self._error_response("This is not a one-time reminder")
            
            # Deactivate the schedule
            schedule.is_active = False
            session.add(schedule)
            session.commit()
            
            return self._ok_response(
                schedule_id=schedule_id,
                deleted=True,
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_delete_all_one_time_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_one_time_reminders function."""
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        
        try:
            count = scheduler_api.deactivate_user_schedules_by_type(
                user_id=user_id,
                schedule_type="one_time",
                session=context.get("session"),
            )
            
            return self._ok_response(
                deleted_count=count,
                type="one_time",
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_delete_all_daily_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_daily_reminders function."""
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        
        try:
            count = scheduler_api.deactivate_user_schedules_by_type(
                user_id=user_id,
                schedule_type="daily",
                session=context.get("session"),
            )
            
            return self._ok_response(
                deleted_count=count,
                type="daily",
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_delete_all_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_reminders function."""
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        
        try:
            count = scheduler_api.deactivate_user_schedules(
                user_id=user_id,
                session=context.get("session"),
            )
            
            return self._ok_response(
                deleted_count=count,
                type="all",
            )
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_send_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send_lesson function."""
        lesson_id = params.get("lesson_id")
        session = context.get("session")
        
        try:
            lesson = self._get_lesson_by_id(lesson_id, session)
            if not lesson:
                return self._error_response(f"Lesson {lesson_id} not found")
            
            return self._ok_response(
                lesson_id=lesson_id,
                title=lesson.title,
                content=lesson.content,
            )
        except Exception as e:
            return self._error_response(str(e))
        
    async def _handle_send_todays_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send_todays_lesson function.
        
        Computes today's lesson from user state, or uses explicit lesson_id if provided.
        Uses compute_current_lesson_state for auto-advance logic (current +1 if inactive yesterday).
        """
        user_id = context.get("user_id")
        session = context.get("session")
        memory_manager = context.get("memory_manager")
        
        if not user_id or not memory_manager:
            return self._error_response("Missing user context")
        
# Explicit lesson_id override from params
        state = None
        lesson_id = params.get("lesson_id")
        if lesson_id is not None:
            try:
                lesson_id = int(lesson_id)
                logger.info(f"send_todays_lesson user={user_id}: explicit lesson_id={lesson_id}")
            except (ValueError, TypeError):
                return self._error_response(f"Invalid lesson_id: {lesson_id}")
        else:
            # Compute today's lesson from state (auto-advance if needed)
            state = compute_current_lesson_state(memory_manager, user_id)
            lesson_id = state["lesson_id"]
            logger.info(f"send_todays_lesson user={user_id}: computed lesson_id={lesson_id}, advanced={state.get('advanced_by_day', False)}")
        
        try:
            lesson = self._get_lesson_by_id(lesson_id, session)
            if not lesson:
                return self._error_response(f"Lesson {lesson_id} not available (check imports)")
            
            return self._ok_response(
                lesson_id=lesson_id,
                title=lesson.title,
                content=lesson.content,
            )
        except Exception as e:
            logger.exception(f"send_todays_lesson error user={user_id} lesson={lesson_id}")
            return self._error_response(f"Failed to load lesson {lesson_id}: {str(e)}")

    async def _handle_set_timezone(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_timezone function."""
        from src.core.timezone import resolve_timezone_name, to_utc
        from src.memories.constants import MemoryKey
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        timezone_str = params.get("timezone")
        session = context.get("session")
        memory_manager = context.get("memory_manager")
        
        # Validate timezone using DRY helper
        is_valid, normalized_tz, error = self._validate_timezone(timezone_str)
        if not is_valid:
            return self._error_response(error)
        
        # Resolve to IANA timezone
        resolved = resolve_timezone_name(normalized_tz)
        if not resolved:
            return self._error_response(f"Could not resolve timezone: {normalized_tz}")
        
        try:
            # Update user record
            from src.models.database import User
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.timezone = resolved
                session.add(user)
                session.commit()
                logger.info(f"Updated user {user_id} timezone to {resolved}")
            
            # Update schedules to maintain preferred local time
            if memory_manager:
                from src.scheduler.domain import is_daily_schedule_family
                
                # Try PREFERRED_LESSON_TIME first, then fallback to checking all memories
                preferred_time = None
                preferred_time_mem = memory_manager.get_memory(user_id, MemoryKey.PREFERRED_LESSON_TIME)
                if preferred_time_mem:
                    preferred_time = preferred_time_mem[0]["value"]
                else:
                    # Fallback: check for any time-related memory (e.g., from test setup)
                    all_memories = memory_manager.get_memories(user_id, category="profile")
                    for mem in all_memories:
                        if "time" in mem.get("key", "").lower() or ":" in mem.get("value", ""):
                            preferred_time = mem.get("value")
                            break
                
                if preferred_time:
                    # Get user's active daily schedules using the context session
                    from src.models.database import Schedule
                    schedules = session.query(Schedule).filter_by(
                        user_id=user_id,
                        is_active=True,
                    ).all()
                    
                    # Update each daily schedule to use the preferred time in new timezone
                    updated_count = 0
                    for schedule in schedules:
                        if schedule.is_active and is_daily_schedule_family(schedule.schedule_type):
                            updated = scheduler_api.update_daily_schedule(
                                schedule_id=schedule.schedule_id,
                                time_str=preferred_time,
                                session=session,
                            )
                            if updated:
                                updated_count += 1
                    
                    if updated_count > 0:
                        logger.info(f"Updated {updated_count} daily schedules to {preferred_time} for timezone change")
            
            return self._ok_response(timezone=resolved)
        except Exception as e:
            logger.exception("Error in set_timezone")
            return self._error_response(str(e))
    
    async def _handle_set_language(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_language function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        language = params.get("language")
        memory_manager = context.get("memory_manager")
        
        # Validate language using DRY helper
        is_valid, normalized_lang, error = self._validate_language(language)
        if not is_valid:
            return self._error_response(error)
        
        try:
            # Store in memory
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.USER_LANGUAGE,
                value=normalized_lang,
                category=MemoryCategory.PROFILE.value,
                source="function_executor",
            )
            
            return self._ok_response(language=normalized_lang)
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_set_preferred_time(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_preferred_time function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        time = params.get("time")
        memory_manager = context.get("memory_manager")
        
        # Validate time using DRY helper
        is_valid, normalized_time, error = self._validate_time(time)
        if not is_valid:
            return self._error_response(error)
        
        try:
            # Store in memory
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.PREFERRED_LESSON_TIME,
                value=normalized_time,
                category=MemoryCategory.PROFILE.value,
                source="function_executor",
            )
            
            return self._ok_response(time=normalized_time)
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_update_profile(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_profile function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        key = params.get("key")
        value = params.get("value")
        memory_manager = context.get("memory_manager")
        
        # Map common profile keys to memory keys
        key_mapping = {
            "name": MemoryKey.FULL_NAME,
            "first_name": MemoryKey.FIRST_NAME,
            "email": "email",
            "background": MemoryKey.PERSONAL_BACKGROUND,
        }
        
        memory_key = key_mapping.get(key, key)
        
        try:
            memory_manager.store_memory(
                user_id=user_id,
                key=memory_key,
                value=value,
                category=MemoryCategory.PROFILE.value,
                source="function_executor",
            )
            
            return self._ok_response(key=key, value=value)
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_confirm_yes(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle confirm_yes function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        from src.models.database import Lesson
        
        user_id = context.get("user_id")
        confirmation_context = params.get("context", "general")
        memory_manager = context.get("memory_manager")
        
        try:
            # Special handling for lesson repeat context
            if confirmation_context == "lesson_repeat" and memory_manager:
                # Get the lesson that was offered for repeat
                offered_memories = memory_manager.get_memory(user_id, MemoryKey.LESSON_REPEAT_OFFERED)
                if offered_memories:
                    lesson_id_str = offered_memories[0].get("value")
                    try:
                        lesson_id = int(lesson_id_str)
                        session = context.get("session")
                        if session:
                            lesson = self._get_lesson_by_id(lesson_id, session)
                            if lesson:
                                # Clear the offered memory after use
                                memory_manager.archive_memories(
                                    user_id, 
                                    [offered_memories[0].get("memory_id")]
                                )
                                return self._ok_response(
                                    confirmed=True,
                                    context=confirmation_context,
                                    lesson_id=lesson_id,
                                    title=lesson.title,
                                    content=lesson.content,
                                )
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid lesson_id in lesson_repeat_offered: {lesson_id_str}")
            
            # Store confirmation
            memory_manager.store_memory(
                user_id=user_id,
                key="user_confirmation",
                value=f"yes:{confirmation_context}",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                ttl_hours=1,
            )
            
            return self._ok_response(confirmed=True, context=confirmation_context)
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_confirm_no(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle confirm_no function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        confirmation_context = params.get("context", "general")
        memory_manager = context.get("memory_manager")
        
        try:
            # Store confirmation
            memory_manager.store_memory(
                user_id=user_id,
                key="user_confirmation")
            
            return self._ok_response(confirmed=False, context=confirmation_context)
        except Exception as e:
            return self._error_response(str(e))
    
    async def _handle_extract_memory(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle extract_memory function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        from src.lessons.state import set_current_lesson
        
        user_id = context.get("user_id")
        key = params.get("key")
        value = params.get("value")
        ttl_hours = params.get("ttl_hours")
        memory_manager = context.get("memory_manager")
        
        logger.info(f"extract_memory called: user_id={user_id}, key={key}, value={value}")
        
        # Route lesson state writes through the centralized helpers
        # This ensures DRY - all lesson progress goes through lesson_state
        if key == MemoryKey.LESSON_CURRENT:
            # Normalize numeric lesson values to int, keep strings like 'continuing'
            parsed = None
            try:
                parsed = int(value)
            except Exception:
                parsed = value
            logger.info(f"extract_memory routing to set_current_lesson: user_id={user_id}, lesson={parsed}")
            set_current_lesson(memory_manager, user_id, parsed)
            return self._ok_response(
                key=key,
                value=value,
                category=MemoryCategory.PROGRESS.value,
                updated=True,
            )

        
        # For non-lesson memories, continue with existing logic
        # Determine category from key (call the helper method)
        category = self._get_memory_category_for_key(key)
        logger.info(f"extract_memory storing: user_id={user_id}, key={key}, value={value}, category={category}")
        
        try:
            # Check for existing memory with same key
            existing = memory_manager.get_memory(user_id, key)
            
            memory_manager.store_memory(
                user_id=user_id,
                key=key,
                value=value,
                category=category,
                source="function_executor",
                ttl_hours=ttl_hours,
            )
            
            logger.info(f"extract_memory stored successfully: user_id={user_id}, key={key}")
            return self._ok_response(
                key=key,
                value=value,
                category=category,
                updated=bool(existing),
            )
        except Exception as e:
            logger.error(f"extract_memory failed: user_id={user_id}, key={key}, error={e}")
            return self._error_response(str(e))
    
    def _get_memory_category_for_key(self, key: str) -> str:
        """Infer memory category from key name."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        # Use centralized key sets from MemoryKey (DRY)
        if key in MemoryKey.PROFILE_KEYS:
            return MemoryCategory.PROFILE.value
        elif key in MemoryKey.PROGRESS_KEYS:
            return MemoryCategory.PROGRESS.value
        else:
            return MemoryCategory.CONVERSATION.value

    async def _handle_set_current_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_current_lesson function."""
        from src.lessons.state import set_current_lesson
        
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        lesson_number = params.get("lesson_number")
        
        try:
            lesson_number = int(lesson_number)
            if not (1 <= lesson_number <= 365):
                return self._error_response(f"Lesson {lesson_number} out of range 1-365")
            
            set_current_lesson(memory_manager, user_id, lesson_number)
            logger.info(f"set_current_lesson: user_id={user_id}, lesson={lesson_number}")
            return self._ok_response(lesson_number=lesson_number)
        except (ValueError, TypeError) as e:
            return self._error_response(f"Invalid lesson number: {lesson_number}")

    async def _handle_forget_memories(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle forget_memories function - AI callable semantic memory deletion."""
        from src.memories.semantic_search import get_semantic_search_service
        
        user_id = context.get("user_id")
        query_text = params.get("query_text")
        session = context.get("session")
        memory_manager = context.get("memory_manager")
        
        if not query_text or not query_text.strip():
            return self._error_response("query_text is required")
        
        if not memory_manager:
            return self._error_response("Missing memory_manager in context")
        
        from src.models.database import Session
        search_service = get_semantic_search_service()
        with Session(bind=session.get_bind()) as search_session:
            results = await search_service.search_memories(
                user_id=user_id,
                query_text=query_text,
                session=search_session,
                limit=10,  # Reasonable default limit
            )
            memory_ids = [memory.memory_id for memory, _ in results]
        
        if not memory_ids:
            return self._error_response("No matching memories found")
        
        archived_count = memory_manager.archive_memories(user_id, memory_ids)
        
        logger.info(f"forgot {archived_count} memories for user {user_id} matching '{query_text}'")
        
        return self._ok_response(
            query_text=query_text,
            found_count=len(memory_ids),
            archived_count=archived_count,
        )


# Global instance
_executor: Optional[FunctionExecutor] = None


def get_function_executor(registry: Optional[FunctionRegistry] = None) -> FunctionExecutor:
    """Get the global function executor instance."""
    global _executor
    if _executor is None:
        _executor = FunctionExecutor(registry)
    return _executor


def reset_executor():
    """Reset the global instance (useful for testing)."""
    global _executor
    _executor = None
