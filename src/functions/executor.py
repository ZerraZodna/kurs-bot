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
        self._handlers["send_next_lesson"] = self._handle_send_next_lesson
        self._handlers["send_todays_lesson"] = self._handle_send_todays_lesson
        self._handlers["mark_lesson_complete"] = self._handle_mark_lesson_complete
        self._handlers["repeat_lesson"] = self._handle_repeat_lesson
        self._handlers["set_lesson_preference"] = self._handle_set_lesson_preference
        
        # Profile handlers
        self._handlers["set_timezone"] = self._handle_set_timezone
        self._handlers["set_language"] = self._handle_set_language
        self._handlers["set_preferred_time"] = self._handle_set_preferred_time
        self._handlers["update_profile"] = self._handle_update_profile
        
        # RAG handlers
        self._handlers["enter_rag"] = self._handle_enter_rag
        self._handlers["exit_rag"] = self._handle_exit_rag
        
        # Confirmation handlers
        self._handlers["confirm_yes"] = self._handle_confirm_yes
        self._handlers["confirm_no"] = self._handle_confirm_no
        
        # Memory extraction handler
        self._handlers["extract_memory"] = self._handle_extract_memory
    
    def register_handler(self, function_name: str, handler: Callable):
        """Register a custom handler for a function."""
        self._handlers[function_name] = handler
        logger.debug(f"Registered handler for function: {function_name}")
    
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
        
        # Validate time format
        is_valid, normalized_time, error = ParameterValidator.validate_time(time)
        if not is_valid:
            return {"ok": False, "error": error}
        
        try:
            schedule = scheduler_api.create_daily_schedule(
                user_id=user_id,
                lesson_id=lesson_id,
                time_str=normalized_time,
                session=context.get("session"),
            )
            return {
                "ok": True,
                "schedule_id": schedule.schedule_id,
                "time": normalized_time,
                "message": message,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_update_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_schedule function."""
        from src.scheduler import api as scheduler_api
        
        schedule_id = params.get("schedule_id")
        time = params.get("time")
        
        # Validate time format
        is_valid, normalized_time, error = ParameterValidator.validate_time(time)
        if not is_valid:
            return {"ok": False, "error": error}
        
        try:
            updated = scheduler_api.update_daily_schedule(
                schedule_id=schedule_id,
                time_str=normalized_time,
                session=context.get("session"),
            )
            if updated:
                return {
                    "ok": True,
                    "schedule_id": updated.schedule_id,
                    "time": normalized_time,
                }
            return {"ok": False, "error": "Schedule not found or update failed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
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
                return {"ok": True, "schedule_id": schedule_id}
            return {"ok": False, "error": "Schedule not found or already inactive"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_query_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query_schedule function."""
        from src.scheduler import api as scheduler_api
        from src.scheduler.domain import is_one_time_schedule_type
        from src.scheduler.memory_helpers import get_schedule_message
        
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        
        try:
            schedules = scheduler_api.get_user_schedules(
                user_id=user_id,
                active_only=True,
                session=context.get("session"),
            )
            
            schedule_list = []
            for s in schedules:
                schedule_data = {
                    "schedule_id": s.schedule_id,
                    "schedule_type": s.schedule_type,
                    "cron_expression": s.cron_expression,
                    "next_send_time": s.next_send_time.isoformat() if s.next_send_time else None,
                    "is_active": s.is_active,
                }
                
                # For one-time reminders, fetch the message from memory
                if is_one_time_schedule_type(s.schedule_type) and memory_manager:
                    message = get_schedule_message(memory_manager, user_id, s.schedule_id)
                    if message:
                        schedule_data["message"] = message
                
                schedule_list.append(schedule_data)
            
            return {
                "ok": True,
                "schedules": schedule_list,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_create_one_time_reminder(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_one_time_reminder function."""
        from src.scheduler import api as scheduler_api
        from src.core.timezone import to_utc
        
        user_id = context.get("user_id")
        run_at = params.get("run_at")
        message = params.get("message", "Reminder")
        
        # Validate datetime
        is_valid, dt_obj, error = ParameterValidator.validate_datetime(run_at)
        if not is_valid:
            return {"ok": False, "error": error}
        
        try:
            # Convert to UTC for storage
            run_at_utc = to_utc(dt_obj)
            schedule = scheduler_api.create_one_time_schedule(
                user_id=user_id,
                run_at=run_at_utc,
                message=message,
                session=context.get("session"),
            )
            return {
                "ok": True,
                "schedule_id": schedule.schedule_id,
                "run_at": run_at_utc.isoformat(),  # Return UTC time for proper display
                "message": message,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
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
                return {"ok": False, "error": "Schedule not found"}
            
            # Verify it's a one-time reminder
            if not is_one_time_schedule_type(schedule.schedule_type):
                return {"ok": False, "error": "This is not a one-time reminder"}
            
            # Deactivate the schedule
            schedule.is_active = False
            session.add(schedule)
            session.commit()
            
            return {
                "ok": True,
                "schedule_id": schedule_id,
                "deleted": True,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
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
            
            return {
                "ok": True,
                "deleted_count": count,
                "type": "one_time",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
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
            
            return {
                "ok": True,
                "deleted_count": count,
                "type": "daily",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_delete_all_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_reminders function."""
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        
        try:
            count = scheduler_api.deactivate_user_schedules(
                user_id=user_id,
                session=context.get("session"),
            )
            
            return {
                "ok": True,
                "deleted_count": count,
                "type": "all",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_send_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send_lesson function."""
        from src.models.database import Lesson
        
        lesson_id = params.get("lesson_id")
        session = context.get("session")
        
        try:
            lesson = session.query(Lesson).filter_by(lesson_id=lesson_id).first()
            if not lesson:
                return {"ok": False, "error": f"Lesson {lesson_id} not found"}
            
            return {
                "ok": True,
                "lesson_id": lesson_id,
                "title": lesson.title,
                "content": lesson.content,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_send_next_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send_next_lesson function."""
        from src.lessons.api import compute_current_lesson_state
        
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        
        try:
            state = compute_current_lesson_state(
                memory_manager=memory_manager,
                user_id=user_id,
            )
            lesson_id = state.get("lesson_id")
            
            if not lesson_id:
                return {"ok": False, "error": "Could not determine next lesson"}
            
            # Get lesson content
            from src.models.database import Lesson
            session = context.get("session")
            lesson = session.query(Lesson).filter_by(lesson_id=lesson_id).first()
            
            if not lesson:
                return {"ok": False, "error": f"Lesson {lesson_id} not found"}
            
            return {
                "ok": True,
                "lesson_id": lesson_id,
                "title": lesson.title,
                "content": lesson.content,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_send_todays_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send_todays_lesson function."""
        # Same as send_next_lesson for now
        return await self._handle_send_next_lesson(params, context)
    
    async def _handle_mark_lesson_complete(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mark_lesson_complete function."""
        from src.lessons.state import record_lesson_completed
        
        user_id = context.get("user_id")
        lesson_id = params.get("lesson_id")
        memory_manager = context.get("memory_manager")
        
        # Use centralized helper for DRY
        if lesson_id:
            result = record_lesson_completed(
                memory_manager,
                user_id,
                lesson_id,
                source="function_executor"
            )
            return {
                "ok": True,
                "lesson_id": lesson_id,
                "marked_complete": True,
                "result": result,
            }
        else:
            return {
                "ok": False,
                "error": "lesson_id is required",
            }
    
    async def _handle_repeat_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle repeat_lesson function."""
        from src.memories.constants import MemoryKey
        
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        
        try:
            # Get last sent lesson
            last_sent = memory_manager.get_memory(user_id, MemoryKey.LAST_SENT_LESSON_ID)
            if not last_sent:
                return {"ok": False, "error": "No previous lesson to repeat"}
            
            lesson_id = int(last_sent[0]["value"])
            
            # Get lesson content
            from src.models.database import Lesson
            session = context.get("session")
            lesson = session.query(Lesson).filter_by(lesson_id=lesson_id).first()
            
            if not lesson:
                return {"ok": False, "error": f"Lesson {lesson_id} not found"}
            
            return {
                "ok": True,
                "lesson_id": lesson_id,
                "title": lesson.title,
                "content": lesson.content,
                "is_repeat": True,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_set_lesson_preference(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_lesson_preference function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        preference = params.get("preference")
        skip_confirmation = params.get("skip_confirmation", False)
        memory_manager = context.get("memory_manager")
        
        try:
            # Store preference
            memory_manager.store_memory(
                user_id=user_id,
                key="lesson_preference",
                value=preference,
                category=MemoryCategory.PREFERENCES.value,
                source="function_executor",
                confidence=1.0,
            )
            
            # Store skip confirmation setting
            if skip_confirmation:
                memory_manager.store_memory(
                    user_id=user_id,
                    key="skip_lesson_confirmation",
                    value="true",
                    category=MemoryCategory.PREFERENCES.value,
                    source="function_executor",
                    confidence=1.0,
                )
            
            return {
                "ok": True,
                "preference": preference,
                "skip_confirmation": skip_confirmation,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_set_timezone(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_timezone function."""
        from src.core.timezone import resolve_timezone_name, to_utc
        from src.memories.constants import MemoryKey
        from src.scheduler import api as scheduler_api
        
        user_id = context.get("user_id")
        timezone_str = params.get("timezone")
        session = context.get("session")
        memory_manager = context.get("memory_manager")
        
        # Validate timezone
        is_valid, normalized_tz, error = ParameterValidator.validate_timezone(timezone_str)
        if not is_valid:
            return {"ok": False, "error": error}
        
        # Resolve to IANA timezone
        resolved = resolve_timezone_name(normalized_tz)
        if not resolved:
            return {"ok": False, "error": f"Could not resolve timezone: {normalized_tz}"}
        
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
            
            return {
                "ok": True,
                "timezone": resolved,
            }
        except Exception as e:
            logger.exception("Error in set_timezone")
            return {"ok": False, "error": str(e)}
    
    async def _handle_set_language(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_language function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        language = params.get("language")
        memory_manager = context.get("memory_manager")
        
        # Validate language
        is_valid, normalized_lang, error = ParameterValidator.validate_language(language)
        if not is_valid:
            return {"ok": False, "error": error}
        
        try:
            # Store in memory
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.PREFERRED_LANGUAGE,
                value=normalized_lang,
                category=MemoryCategory.PROFILE.value,
                source="function_executor",
                confidence=1.0,
            )
            
            return {
                "ok": True,
                "language": normalized_lang,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_set_preferred_time(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set_preferred_time function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        time = params.get("time")
        memory_manager = context.get("memory_manager")
        
        # Validate time
        is_valid, normalized_time, error = ParameterValidator.validate_time(time)
        if not is_valid:
            return {"ok": False, "error": error}
        
        try:
            # Store in memory
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.PREFERRED_LESSON_TIME,
                value=normalized_time,
                category=MemoryCategory.PROFILE.value,
                source="function_executor",
                confidence=1.0,
            )
            
            return {
                "ok": True,
                "time": normalized_time,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
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
            "goals": MemoryKey.LEARNING_GOAL,
        }
        
        memory_key = key_mapping.get(key, key)
        
        try:
            memory_manager.store_memory(
                user_id=user_id,
                key=memory_key,
                value=value,
                category=MemoryCategory.PROFILE.value,
                source="function_executor",
                confidence=1.0,
            )
            
            return {
                "ok": True,
                "key": key,
                "value": value,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_enter_rag(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle enter_rag function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        
        try:
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.RAG_MODE_ENABLED,
                value="true",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                confidence=1.0,
                ttl_hours=24 * 7,  # 1 week default
            )
            
            return {"ok": True, "rag_mode": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_exit_rag(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle exit_rag function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        
        try:
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.RAG_MODE_ENABLED,
                value="false",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                confidence=1.0,
            )
            
            return {"ok": True, "rag_mode": False}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_confirm_yes(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle confirm_yes function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        user_id = context.get("user_id")
        confirmation_context = params.get("context", "general")
        memory_manager = context.get("memory_manager")
        
        try:
            # Store confirmation
            memory_manager.store_memory(
                user_id=user_id,
                key="user_confirmation",
                value=f"yes:{confirmation_context}",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                confidence=1.0,
                ttl_hours=1,
            )
            
            return {
                "ok": True,
                "confirmed": True,
                "context": confirmation_context,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
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
                key="user_confirmation",
                value=f"no:{confirmation_context}",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                confidence=1.0,
                ttl_hours=1,
            )
            
            return {
                "ok": True,
                "confirmed": False,
                "context": confirmation_context,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_extract_memory(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle extract_memory function."""
        from src.memories.constants import MemoryCategory, MemoryKey
        from src.lessons.state import set_current_lesson, record_lesson_completed
        
        user_id = context.get("user_id")
        key = params.get("key")
        value = params.get("value")
        confidence = params.get("confidence", 0.7)
        ttl_hours = params.get("ttl_hours")
        memory_manager = context.get("memory_manager")
        
        # Validate confidence threshold
        if confidence < 0.7:
            return {
                "ok": False,
                "error": f"Confidence {confidence} below threshold (0.7)",
                "key": key,
            }
        
        # Route lesson state writes through the centralized helpers
        # This ensures DRY - all lesson progress goes through lesson_state
        if key == MemoryKey.LESSON_CURRENT:
            # Normalize numeric lesson values to int, keep strings like 'continuing'
            parsed = None
            try:
                parsed = int(value)
            except Exception:
                parsed = value
            set_current_lesson(memory_manager, user_id, parsed)
            return {
                "ok": True,
                "key": key,
                "value": value,
                "confidence": confidence,
                "category": MemoryCategory.PROGRESS.value,
                "updated": True,
            }
        elif key == MemoryKey.LESSON_COMPLETED:
            # Route through centralized helper for DRY
            try:
                lesson_id = int(value)
                result = record_lesson_completed(
                    memory_manager, 
                    user_id, 
                    lesson_id,
                    source="function_executor"
                )
                return {
                    "ok": True,
                    "key": key,
                    "value": value,
                    "confidence": confidence,
                    "category": MemoryCategory.PROGRESS.value,
                    "updated": True,
                    "result": result,
                }
            except (ValueError, TypeError):
                return {"ok": False, "error": f"Invalid lesson_id: {value}"}
        
        # For non-lesson memories, continue with existing logic
        # Determine category from key
        category = self._infer_memory_category(key)
        
        try:
            # Check for existing memory with same key
            existing = memory_manager.get_memory(user_id, key)
            
            memory_manager.store_memory(
                user_id=user_id,
                key=key,
                value=value,
                category=category,
                source="function_executor",
                confidence=confidence,
                ttl_hours=ttl_hours,
            )
            
            return {
                "ok": True,
                "key": key,
                "value": value,
                "confidence": confidence,
                "category": category,
                "updated": bool(existing),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _infer_memory_category(self, key: str) -> str:
        """Infer memory category from key name."""
        from src.memories.constants import MemoryCategory, MemoryKey
        
        profile_keys = [
            MemoryKey.FULL_NAME, MemoryKey.FIRST_NAME, MemoryKey.NAME,
            MemoryKey.USER_LANGUAGE, MemoryKey.PREFERRED_LESSON_TIME,
            MemoryKey.PERSONAL_BACKGROUND,
        ]
        preference_keys = [
            "learning_style", "preferred_tone",
            "contact_frequency", "lesson_preference",
        ]
        progress_keys = [
            MemoryKey.LESSON_COMPLETED, MemoryKey.LESSON_CURRENT,
            "milestone", "insight",
        ]
        
        if key in profile_keys:
            return MemoryCategory.PROFILE.value
        elif key in preference_keys:
            return MemoryCategory.PREFERENCES.value
        elif key in progress_keys:
            return MemoryCategory.PROGRESS.value
        else:
            return MemoryCategory.CONVERSATION.value


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
