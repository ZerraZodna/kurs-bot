from typing import TYPE_CHECKING, Any, Dict

from src.core.timezone import format_dt_in_timezone, get_user_timezone_from_db, to_utc
from src.models.database import Schedule
from src.scheduler import api as scheduler_api
from src.scheduler.domain import is_one_time_schedule_type
from src.scheduler.memory_helpers import get_schedule_message

if TYPE_CHECKING:
    from ..executor import FunctionExecutor


class ScheduleHandler:
    """Handles all schedule-related function calls. Delegated from FunctionExecutor."""

    def __init__(self, executor: "FunctionExecutor") -> None:
        self.executor = executor

    async def create_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_schedule."""
        user_id = context.get("user_id")
        time = params.get("time")
        message = params.get("message", "Time for your ACIM lesson")
        lesson_id = params.get("lesson_id")

        is_valid, normalized_time, error = self.executor._validate_time(time)
        if not is_valid:
            return self.executor._error_response(error)

        try:
            schedule = scheduler_api.create_daily_schedule(
                user_id=user_id,
                lesson_id=lesson_id,
                time_str=normalized_time,
                session=context.get("session"),
            )
            return self.executor._ok_response(
                schedule_id=schedule.schedule_id,
                time=normalized_time,
                message=message,
            )
        except Exception as e:
            return self.executor._error_response(str(e))

    async def update_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update_schedule."""
        schedule_id = params.get("schedule_id")
        time = params.get("time")

        is_valid, normalized_time, error = self.executor._validate_time(time)
        if not is_valid:
            return self.executor._error_response(error)

        try:
            updated = scheduler_api.update_daily_schedule(
                schedule_id=schedule_id,
                time_str=normalized_time,
                session=context.get("session"),
            )
            if updated:
                return self.executor._ok_response(
                    schedule_id=updated.schedule_id,
                    time=normalized_time,
                )
            return self.executor._error_response("Schedule not found")
        except Exception as e:
            return self.executor._error_response(str(e))

    async def delete_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_schedule."""
        schedule_id = params.get("schedule_id")

        try:
            result = scheduler_api.deactivate_schedule(
                schedule_id=schedule_id,
                session=context.get("session"),
            )
            if result:
                return self.executor._ok_response(schedule_id=schedule_id)
            return self.executor._error_response("Schedule not found")
        except Exception as e:
            return self.executor._error_response(str(e))

    async def query_schedule(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query_schedule."""
        user_id = context.get("user_id")
        session = context.get("session")
        memory_manager = context.get("memory_manager")

        tz_name = get_user_timezone_from_db(session, user_id) if session else "UTC"

        try:
            schedules = scheduler_api.get_user_schedules(
                user_id=user_id,
                active_only=True,
                session=session,
            )

            schedule_list = []
            for s in schedules:
                local_time = None
                if s.next_send_time:
                    local_dt, _ = format_dt_in_timezone(s.next_send_time, tz_name)
                    local_time = local_dt.isoformat()

                schedule_data = {
                    "schedule_id": s.schedule_id,
                    "schedule_type": s.schedule_type,
                    "cron_expression": s.cron_expression,
                    "next_send_time": local_time,
                    "is_active": s.is_active,
                }

                if is_one_time_schedule_type(s.schedule_type) and memory_manager:
                    message = get_schedule_message(memory_manager, user_id, s.schedule_id)
                    if message:
                        schedule_data["message"] = message

                schedule_list.append(schedule_data)

            return self.executor._ok_response(schedules=schedule_list, timezone=tz_name)
        except Exception as e:
            return self.executor._error_response(str(e))

    async def create_one_time_reminder(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_one_time_reminder."""
        user_id = context.get("user_id")
        run_at = params.get("run_at")
        message = params.get("message", "Reminder")

        is_valid, dt_obj, error = self.executor._validate_datetime(run_at)
        if not is_valid:
            return self.executor._error_response(error)

        try:
            run_at_utc = to_utc(dt_obj)
            schedule = scheduler_api.create_one_time_schedule(
                user_id=user_id,
                run_at=run_at_utc,
                message=message,
                session=context.get("session"),
            )
            return self.executor._ok_response(
                schedule_id=schedule.schedule_id,
                run_at=run_at_utc.isoformat(),
                message=message,
            )
        except Exception as e:
            return self.executor._error_response(str(e))

    async def delete_one_time_reminder(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_one_time_reminder."""
        user_id = context.get("user_id")
        schedule_id = params.get("schedule_id")
        session = context.get("session")

        try:
            schedule = session.query(Schedule).filter_by(schedule_id=schedule_id, user_id=user_id).first()
            if not schedule:
                return self.executor._error_response("Schedule not found")

            if not is_one_time_schedule_type(schedule.schedule_type):
                return self.executor._error_response("Not a one-time reminder")

            schedule.is_active = False
            session.add(schedule)
            session.commit()

            return self.executor._ok_response(schedule_id=schedule_id, deleted=True)
        except Exception as e:
            return self.executor._error_response(str(e))

    async def delete_all_one_time_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_one_time_reminders."""
        user_id = context.get("user_id")

        try:
            count = scheduler_api.deactivate_user_schedules_by_type(
                user_id=user_id,
                schedule_type="one_time",
                session=context.get("session"),
            )
            return self.executor._ok_response(deleted_count=count, type="one_time")
        except Exception as e:
            return self.executor._error_response(str(e))

    async def delete_all_daily_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_daily_reminders."""
        user_id = context.get("user_id")

        try:
            count = scheduler_api.deactivate_user_schedules_by_type(
                user_id=user_id,
                schedule_type="daily",
                session=context.get("session"),
            )
            return self.executor._ok_response(deleted_count=count, type="daily")
        except Exception as e:
            return self.executor._error_response(str(e))

    async def delete_all_reminders(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_all_reminders."""
        user_id = context.get("user_id")

        try:
            count = scheduler_api.deactivate_user_schedules(
                user_id=user_id,
                session=context.get("session"),
            )
            return self.executor._ok_response(deleted_count=count, type="all")
        except Exception as e:
            return self.executor._error_response(str(e))

    async def handle(self, func_name: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to specific handler based on func_name."""
        method_name = func_name.replace("-", "_")
        method = getattr(self, method_name, None)
        if method:
            return await method(params, context)
        raise ValueError(f"Unknown schedule function: {func_name}")
