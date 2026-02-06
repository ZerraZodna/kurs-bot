import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from src.services.scheduler.memory_utils import get_user_language
from src.services.scheduler.message_utils import translate_text_sync

from src.services.memory_manager import MemoryManager
from src.services import scheduler as _scheduler_pkg
from src.models.database import SessionLocal, Schedule, User
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
                allow_duplicates=False,
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
                            # Accept times like "9", "09", "9:00", "09:00"
                            m = re.search(r"(\d{1,2}(?::\d{2})?)", original_text)
                            # If not found in original_text, try assistant response
                            if not m:
                                assistant_response = context.get("assistant_response", "") or ""
                                m = re.search(r"(\d{1,2}(?::\d{2})?)", assistant_response)
                            if m:
                                time_str = m.group(1)
                                # Normalize hour-only like "9" -> "9:00"
                                if ":" not in time_str:
                                    time_str = f"{int(time_str):02d}:00"
                        if not time_str:
                            result.update({"ok": False, "error": "missing_time"})
                        else:
                            # Persist preferred lesson time as memory so scheduler workers/processes
                            # that react to this memory will update the actual scheduled job.
                            try:
                                self.memory_manager.store_memory(
                                    user_id,
                                    "preferred_lesson_time",
                                    time_str,
                                    category="profile",
                                    source="trigger_dispatcher",
                                )
                            except Exception:
                                # best-effort; continue to attempt immediate schedule update
                                pass

                            try:
                                # Also attempt immediate schedule recreation for responsiveness.
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
                                result.update({"ok": True, "schedule_id": new.schedule_id, "note": "preferred_time_set"})
                            except Exception as e:
                                # If immediate recreation fails, we still return ok since memory was set
                                result.update({"ok": True, "note": "preferred_time_set_but_create_failed", "error": str(e)})
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

            elif action == "set_timezone":
                # Expect either explicit timezone string in context or infer from original_text
                tz = None
                if isinstance(context, dict):
                    tz = context.get("timezone") or context.get("tz")
                    original_text = context.get("original_text") or context.get("text") or ""
                else:
                    original_text = ""

                # Try simple extraction from text like "I'm in Oslo" or "My timezone is Europe/Oslo"
                if not tz and original_text:
                    import re
                    # Match a variety of natural phrases, e.g.:
                    # "I'm in Oslo", "I live in Oslo", "My timezone is Europe/Oslo",
                    # "Set my timezone to Oslo", "Set timezone to Europe/Oslo"
                    m = re.search(r"(?:timezone is|time zone is|time zone to|timezone to|set(?: my)? timezone to|set timezone to|set my time zone to|i am in|i'm in|i live in)\s+([A-Za-z/_\s-]+)", original_text, re.IGNORECASE)
                    if m:
                        tz = m.group(1).strip()
                    else:
                        # Maybe user provided a one-word city (e.g. "OSLO") — try to extract a single token
                        m2 = re.search(r"^\s*([A-Za-z]{2,}[\sA-Za-z]*)\s*$", original_text)
                        if m2:
                            candidate = m2.group(1).strip()
                            # ignore short inputs that are likely not a timezone
                            if len(candidate) > 2:
                                tz = candidate

                # Normalize common city names to IANA tz names
                if tz:
                    tz_raw = tz.strip()
                    tz_lookup = {
                        "oslo": "Europe/Oslo",
                        "bergen": "Europe/Oslo",
                        "stockholm": "Europe/Stockholm",
                        "copenhagen": "Europe/Copenhagen",
                        "london": "Europe/London",
                        "new york": "America/New_York",
                        "los angeles": "America/Los_Angeles",
                    }
                    key = tz_raw.lower()
                    if key in tz_lookup:
                        tz_name = tz_lookup[key]
                    else:
                        # Accept already valid IANA names like Europe/Oslo or UTC
                        tz_name = tz_raw.replace(" ", "_")

                    # Validate via zoneinfo
                    try:
                        from zoneinfo import ZoneInfo
                        ZoneInfo(tz_name)
                    except Exception:
                        result.update({"ok": False, "error": f"invalid_timezone: {tz_name}"})
                        self._audit(user_id, match.get("trigger_id"), action, {"context": context, "result": result})
                        return result

                    # Persist on user record and memory
                    try:
                        # Prefer direct DB update
                        u = self.db.query(User).filter_by(user_id=user_id).first()
                        if u is not None:
                            u.timezone = tz_name
                            self.db.add(u)
                            self.db.commit()

                        # Also store as memory for compatibility
                        self.memory_manager.store_memory(user_id, "user_timezone", tz_name, category="profile", source="trigger_dispatcher")

                        # Update existing daily schedules to reflect new timezone
                        try:
                            SchedulerService = _scheduler_pkg.SchedulerService
                            # fetch active daily schedules for user
                            active_schedules = self.db.query(Schedule).filter_by(user_id=user_id, is_active=True, schedule_type="daily").all()
                            for sched in active_schedules:
                                # determine intended local time
                                # try preferred_lesson_time memory first
                                preferred = self.memory_manager.get_memory(user_id, "preferred_lesson_time")
                                if preferred and preferred[0].get("value"):
                                    time_str = preferred[0].get("value")
                                else:
                                    # fall back to using next_send_time (UTC) converted to new tz
                                    if sched.next_send_time:
                                        try:
                                            local_dt = sched.next_send_time.astimezone(ZoneInfo(tz_name))
                                            time_str = f"{local_dt.hour:02d}:{local_dt.minute:02d}"
                                        except Exception:
                                            time_str = None
                                    else:
                                        time_str = None

                                # deactivate old schedule and create a new one at same local time
                                try:
                                    SchedulerService.deactivate_schedule(sched.schedule_id)
                                except Exception:
                                    pass

                                if time_str:
                                    try:
                                        SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=sched.lesson_id, time_str=time_str, session=self.db)
                                    except Exception:
                                        # ignore per-schedule failures
                                        pass

                        except Exception:
                            # ignore scheduler update failures
                            pass

                        result.update({"ok": True, "timezone": tz_name})

                        # Send short confirmation to user (immediate feedback)
                        try:
                            # build concise confirmation and translate to user's language
                            conf_text = f"Okay — timezone set to {tz_name}. I'll use local time for your reminders."
                            try:
                                user_lang = get_user_language(self.memory_manager, user_id)
                                if user_lang and user_lang.lower() not in ("english", "en"):
                                    try:
                                        conf_text = translate_text_sync(conf_text, user_lang)
                                    except Exception:
                                        # translation failed; keep original
                                        pass
                            except Exception:
                                pass

                            user = self.db.query(User).filter_by(user_id=user_id).first()
                            if user and getattr(user, 'external_id', None):
                                try:
                                    import asyncio
                                    chat_id = int(user.external_id)
                                    asyncio.run(_scheduler_pkg.send_message(chat_id, conf_text))
                                except Exception:
                                    # ignore send failures
                                    pass
                        except Exception:
                            pass
                    except Exception as e:
                        try:
                            self.db.rollback()
                        except Exception:
                            pass
                        result.update({"ok": False, "error": str(e)})


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
