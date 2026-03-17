import logging
from typing import TYPE_CHECKING, Any, Dict

from src.core.timezone import resolve_timezone_name
from src.lessons.state import compute_current_lesson_state, set_current_lesson
from src.models.database import User

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from ..executor import FunctionExecutor


class LessonProfileHandler:
    """Lesson and profile function handlers."""

    def __init__(self, executor: "FunctionExecutor") -> None:
        self.executor = executor

    async def send_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        lesson_id = params.get("lesson_id")
        session = context.get("session")

        try:
            lesson = self.executor._get_lesson_by_id(lesson_id, session)
            if not lesson:
                return self.executor._error_response(f"Lesson {lesson_id} not found")

            return self.executor._ok_response(
                lesson_id=lesson_id,
                title=lesson.title,
                content=lesson.content,
            )
        except Exception as e:
            return self.executor._error_response(str(e))

    async def send_todays_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        session = context.get("session")
        memory_manager = context.get("memory_manager")

        if not user_id or not memory_manager:
            return self.executor._error_response("Missing user context")

        lesson_id = params.get("lesson_id")
        if lesson_id is not None:
            try:
                lesson_id = int(lesson_id)
            except (ValueError, TypeError):
                return self.executor._error_response(f"Invalid lesson_id: {lesson_id}")
        else:
            state = compute_current_lesson_state(memory_manager, user_id)
            lesson_id = state["lesson_id"]

        try:
            lesson = self.executor._get_lesson_by_id(lesson_id, session)
            if not lesson:
                return self.executor._error_response(f"Lesson {lesson_id} not available")

            return self.executor._ok_response(
                lesson_id=lesson_id,
                title=lesson.title,
                content=lesson.content,
            )
        except Exception as e:
            return self.executor._error_response(f"Failed to load lesson {lesson_id}: {str(e)}")

    async def set_current_lesson(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        memory_manager = context.get("memory_manager")
        lesson_number = params.get("lesson_number")

        try:
            lesson_number = int(lesson_number)
            if not (1 <= lesson_number <= 365):
                return self.executor._error_response(f"Lesson {lesson_number} out of range 1-365")

            set_current_lesson(memory_manager, user_id, lesson_number)
            return self.executor._ok_response(lesson_number=lesson_number)
        except (ValueError, TypeError):
            return self.executor._error_response(f"Invalid lesson number: {lesson_number}")

    async def set_timezone(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        timezone_str = params.get("timezone")
        session = context.get("session")

        is_valid, normalized_tz, error = self.executor._validate_timezone(timezone_str)
        if not is_valid:
            return self.executor._error_response(error)

        resolved = resolve_timezone_name(normalized_tz)
        if not resolved:
            return self.executor._error_response(f"Could not resolve timezone: {normalized_tz}")

        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.timezone = resolved
                session.commit()

            # Migrate daily schedules to preserve preferred local time
            from datetime import timedelta

            from src.core.timezone import parse_local_time_to_utc, utc_now
            from src.scheduler import api as scheduler_api

            memory_manager = context.get("memory_manager")
            if memory_manager:
                preferred_mem = memory_manager.get_memory(user_id, "preferred_lesson_time")
                if preferred_mem:
                    preferred_time = preferred_mem[0]["value"]
                    try:
                        schedules = scheduler_api.get_user_schedules(user_id=user_id, session=session)
                        for s in schedules:
                            if s.schedule_type == "daily":
                                utc_next = parse_local_time_to_utc(preferred_time, resolved, utc_now())
                                s.cron_expression = f"{utc_next.minute} {utc_next.hour} * * *"
                                utc_current = utc_now()
                                s.next_send_time = utc_next if utc_next > utc_current else utc_next + timedelta(days=1)
                        session.commit()
                    except Exception as mig_e:
                        logger.warning(f"Schedule migration failed: {mig_e}")

            return self.executor._ok_response(timezone=resolved)
        except Exception as e:
            return self.executor._error_response(str(e))

    async def handle(self, func_name: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        method_name = func_name.replace("-", "_")
        method = getattr(self, method_name, None)
        if method:
            return await method(params, context)
        raise ValueError(f"Unknown lesson/profile function: {func_name}")
