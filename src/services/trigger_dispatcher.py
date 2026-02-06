import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone

from src.services.memory_manager import MemoryManager
from src.services import scheduler as _scheduler_pkg
from src.models.database import SessionLocal, Schedule
from src.config import settings

logger = logging.getLogger(__name__)


class TriggerDispatcher:
    """Dispatches matched triggers to concrete action handlers."""

    def __init__(self, db=None, memory_manager: MemoryManager = None):
        self.db = db or SessionLocal()
        self.memory_manager = memory_manager or MemoryManager(self.db)

    def _audit(self, user_id: int, trigger_id: int, action_type: str, details: Dict[str, Any]):
        payload = json.dumps({
            "trigger_id": trigger_id,
            "action_type": action_type,
            "details": details,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # Store audit entry as a conversation memory (no schema change required)
        try:
            self.memory_manager.store_memory(
                user_id=user_id,
                key="trigger_audit",
                value=payload,
                category="audit",
                source="trigger_dispatcher",
                ttl_hours=24 * 30,
                allow_duplicates=True,
                generate_embedding=False,
            )
        except Exception as e:
            logger.warning(f"Failed to write trigger audit memory: {e}")

    def dispatch(self, match: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a single match.

        match: {trigger_id, name, action_type, score, threshold}
        context should contain at least `user_id` and optional payload keys depending on action
        """
        action = match.get("action_type")
        user_id = context.get("user_id")
        result = {"ok": False, "action": action}

        try:
            logger.info(f"Dispatching trigger action={action} for user={user_id} match={match}")
            if action == "create_schedule":
                # Expect schedule_spec in context: {schedule_type, time_str, lesson_id}
                spec = context.get("schedule_spec") or {}
                # Idempotency: avoid creating duplicate schedule for same user/time
                cron = spec.get("cron_expression")
                if cron:
                    existing = self.db.query(Schedule).filter_by(user_id=user_id, cron_expression=cron, is_active=True).first()
                    if existing:
                        result.update({"ok": True, "note": "already_exists", "schedule_id": existing.schedule_id})
                        self._audit(user_id, match.get("trigger_id"), action, {"note": "already_exists"})
                        return result

                # Use scheduler helper - we attempt daily creation when time_str provided
                if spec.get("schedule_type") == "daily" and spec.get("time_str"):
                    schedule = _scheduler_pkg.SchedulerService.create_daily_schedule(
                        user_id=user_id,
                        lesson_id=spec.get("lesson_id"),
                        time_str=spec.get("time_str"),
                        session=self.db,
                    )
                    result.update({"ok": True, "schedule_id": schedule.schedule_id})
                else:
                    # Fallback: record request in memory
                    self.memory_manager.store_memory(user_id, "schedule_request_pending", "true", category="conversation")
                    result.update({"ok": True, "note": "deferred"})

            elif action == "update_schedule":
                # Expect schedule_id and updates in context
                schedule_id = context.get("schedule_id")
                updates = context.get("updates", {})
                if not schedule_id:
                    # Attempt to infer target schedule and updates from context
                    # If user provided a new time in the original_text, apply it to their active schedule
                    original_text = context.get("original_text", "") or ""
                    # Try to find the user's active daily lesson schedule (don't touch other reminders)
                    sched = self.db.query(Schedule).filter_by(user_id=user_id, is_active=True, schedule_type="daily").first()
                    if not sched:
                        result.update({"ok": False, "error": "missing_schedule_id"})
                    else:
                        # If updates contain time_str, use it; otherwise try to extract HH:MM from text
                        time_str = updates.get("time_str")
                        if not time_str:
                            import re
                            m = re.search(r"(\d{1,2}:\d{2})", original_text)
                            if m:
                                time_str = m.group(1)

                        if not time_str:
                            result.update({"ok": False, "error": "missing_time"})
                        else:
                            try:
                                new = _scheduler_pkg.SchedulerService.create_daily_schedule(
                                    user_id=sched.user_id,
                                    lesson_id=sched.lesson_id,
                                    time_str=time_str,
                                    session=self.db,
                                )
                                # deactivate old
                                sched.is_active = False
                                self.db.add(sched)
                                self.db.commit()
                                result.update({"ok": True, "schedule_id": new.schedule_id})
                            except Exception as e:
                                result.update({"ok": False, "error": str(e)})
                else:
                    sched = self.db.query(Schedule).filter_by(schedule_id=schedule_id).first()
                    if not sched:
                        result.update({"ok": False, "error": "not_found"})
                    else:
                        # apply simple updates
                        if updates.get("time_str"):
                            # recreate daily schedule
                            try:
                                new = _scheduler_pkg.SchedulerService.create_daily_schedule(
                                    user_id=sched.user_id,
                                    lesson_id=sched.lesson_id,
                                    time_str=updates.get("time_str"),
                                    session=self.db,
                                )
                                # deactivate old
                                sched.is_active = False
                                self.db.add(sched)
                                self.db.commit()
                                result.update({"ok": True, "schedule_id": new.schedule_id})
                            except Exception as e:
                                result.update({"ok": False, "error": str(e)})
                        else:
                            result.update({"ok": False, "error": "no_supported_update_fields"})

            elif action == "next_lesson":
                # Move user to next lesson (idempotent)
                lesson_id = context.get("lesson_id")
                if not lesson_id:
                    result.update({"ok": False, "error": "missing_lesson_id"})
                else:
                    # set next lesson in memories
                    self.memory_manager.set_next_lesson(user_id, int(lesson_id))
                    result.update({"ok": True, "lesson_id": int(lesson_id)})

            elif action == "enter_rag":
                # Persist rag_mode on user as a memory
                self.memory_manager.store_memory(user_id, "rag_mode", "on", category="conversation", source="trigger_dispatcher")
                result.update({"ok": True})

            elif action == "exit_rag":
                self.memory_manager.store_memory(user_id, "rag_mode", "off", category="conversation", source="trigger_dispatcher")
                result.update({"ok": True})

            else:
                result.update({"ok": False, "error": "unknown_action"})

            # Audit
            self._audit(user_id, match.get("trigger_id"), action, {"context": context, "result": result})

        except Exception as e:
            logger.exception("Error dispatching trigger")
            result.update({"ok": False, "error": str(e)})

        return result


# module-level convenience
_dispatcher: TriggerDispatcher = None


def get_trigger_dispatcher(db=None, memory_manager: MemoryManager = None) -> TriggerDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TriggerDispatcher(db=db, memory_manager=memory_manager)
    return _dispatcher
