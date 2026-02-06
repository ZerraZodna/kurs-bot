import logging
import json
from typing import Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from src.services.scheduler.memory_utils import get_user_language
from src.services.scheduler.message_utils import translate_text_sync

from src.services.memory_manager import MemoryManager
from src.services import scheduler as _scheduler_pkg
from src.services.scheduler import manager as schedule_manager
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

    def _parse_run_at(self, run_at_val) -> "datetime | None":
        """Attempt to parse run_at values from multiple formats."""
        try:
            if run_at_val is None:
                return None
            if isinstance(run_at_val, str):
                try:
                    return datetime.fromisoformat(run_at_val)
                except Exception:
                    try:
                        from dateutil import parser as _dp

                        return _dp.parse(run_at_val)
                    except Exception:
                        return None
            if isinstance(run_at_val, (int, float)):
                return datetime.fromtimestamp(int(run_at_val), timezone.utc)
        except Exception:
            return None

    def _create_one_time_from_spec(self, user_id: int, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Create a one-time schedule from structured spec. Returns a partial result dict."""
        run_at_val = spec.get("run_at")
        run_at_dt = self._parse_run_at(run_at_val)
        if run_at_dt is None:
            # Could not parse run_at -> defer and ask assistant/user to clarify
            try:
                self.memory_manager.store_memory(user_id, "schedule_request_pending", "true", category="conversation")
            except Exception:
                pass
            return {"ok": True, "note": "deferred", "error": "invalid_run_at"}

        # Ensure timezone-aware UTC
        if run_at_dt.tzinfo is None:
            run_at_dt = run_at_dt.replace(tzinfo=timezone.utc)

        try:
            schedule = _scheduler_pkg.SchedulerService.create_one_time_schedule(
                user_id=user_id,
                run_at=run_at_dt,
                message=spec.get("message", "Reminder"),
                session=self.db,
            )
            return {"ok": True, "schedule_id": schedule.schedule_id}
        except Exception as e:
            logger.warning(f"Failed to create one-time schedule: {e}")
            try:
                self.memory_manager.store_memory(user_id, "schedule_request_pending", "true", category="conversation")
            except Exception:
                pass
            return {"ok": True, "note": "deferred", "error": str(e)}

    def _handle_create_schedule(self, match: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        spec = context.get("schedule_spec") or {}
        result: Dict[str, Any] = {"ok": False, "action": "create_schedule"}

        # Idempotency: avoid creating duplicate schedule for same user/time
        cron = spec.get("cron_expression")
        if cron:
            existing = next((s for s in schedule_manager.get_user_schedules(user_id, active_only=True, session=self.db) if s.cron_expression == cron), None)
            if existing:
                result.update({"ok": True, "note": "already_exists", "schedule_id": existing.schedule_id})
                return result

        # Use scheduler helper - attempt daily creation when time_str provided
        if spec.get("schedule_type") == "daily" and spec.get("time_str"):
            schedule = _scheduler_pkg.SchedulerService.create_daily_schedule(
                user_id=user_id,
                lesson_id=spec.get("lesson_id"),
                time_str=spec.get("time_str"),
                session=self.db,
            )
            result.update({"ok": True, "schedule_id": schedule.schedule_id})
            return result

        # One-time via structured spec
        if spec.get("schedule_type") and spec.get("schedule_type").startswith("one_time"):
            return self._create_one_time_from_spec(user_id, spec)

        # Fallback: try to infer a one-time reminder from texts
        original_text = context.get("original_text", "") or ""
        assistant_resp = context.get("assistant_response", "") or ""
        text_to_search = f"{original_text}\n{assistant_resp}"

        try:
            import re
            from datetime import timedelta

            m_min = re.search(r"in\s+(\d+)\s+minutes?", text_to_search, re.IGNORECASE)
            m_hour = re.search(r"in\s+(\d+)\s+hours?", text_to_search, re.IGNORECASE)
            run_at_dt = None
            if m_min:
                minutes = int(m_min.group(1))
                run_at_dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            elif m_hour:
                hours = int(m_hour.group(1))
                run_at_dt = datetime.now(timezone.utc) + timedelta(hours=hours)

            if run_at_dt:
                # Try to extract a quoted message to use as the reminder message
                qm = re.search(r"[\"'“](.+?)[\"'”]", text_to_search)
                message_text = spec.get("message") or (qm.group(1) if qm else text_to_search.strip())
                schedule = _scheduler_pkg.SchedulerService.create_one_time_schedule(
                    user_id=user_id,
                    run_at=run_at_dt,
                    message=message_text,
                    session=self.db,
                )
                result.update({"ok": True, "schedule_id": schedule.schedule_id, "note": "one_time_created_inferred"})
                return result
            else:
                # Could not infer -> record request in memory for later handling
                try:
                    self.memory_manager.store_memory(user_id, "schedule_request_pending", "true", category="conversation")
                except Exception:
                    pass
                result.update({"ok": True, "note": "deferred"})
                return result
        except Exception as e:
            logger.warning(f"Failed to infer one-time schedule: {e}")
            try:
                self.memory_manager.store_memory(user_id, "schedule_request_pending", "true", category="conversation")
            except Exception:
                pass
            result.update({"ok": True, "note": "deferred", "error": str(e)})
            return result

    def _handle_update_schedule(self, match: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        schedule_id = context.get("schedule_id")
        updates = context.get("updates", {})
        result: Dict[str, Any] = {"ok": False, "action": "update_schedule"}

        if not schedule_id:
            original_text = context.get("original_text", "") or ""
            sched = schedule_manager.find_active_daily_schedule(user_id, session=self.db)
            if not sched:
                result.update({"ok": False, "error": "missing_schedule_id"})
                return result

            time_str = updates.get("time_str")
            if not time_str:
                import re
                m = re.search(r"(\d{1,2}(?::\d{2})?)", original_text)
                if not m:
                    assistant_response = context.get("assistant_response", "") or ""
                    m = re.search(r"(\d{1,2}(?::\d{2})?)", assistant_response)
                if m:
                    time_str = m.group(1)
                    if ":" not in time_str:
                        time_str = f"{int(time_str):02d}:00"

            if not time_str:
                result.update({"ok": False, "error": "missing_time"})
                return result

            try:
                self.memory_manager.store_memory(
                    user_id,
                    "preferred_lesson_time",
                    time_str,
                    category="profile",
                    source="trigger_dispatcher",
                )
            except Exception:
                pass

            try:
                updated = _scheduler_pkg.SchedulerService.update_daily_schedule(sched.schedule_id, time_str, session=self.db)
                if updated:
                    result.update({"ok": True, "schedule_id": updated.schedule_id, "note": "preferred_time_set"})
                else:
                    result.update({"ok": False, "error": "update_failed"})
            except Exception as e:
                result.update({"ok": True, "note": "preferred_time_set_but_update_failed", "error": str(e)})
            return result

        # explicit schedule_id path
        sched = self.db.query(Schedule).filter_by(schedule_id=schedule_id).first()
        if not sched:
            result.update({"ok": False, "error": "not_found"})
            return result

        if updates.get("time_str"):
            try:
                updated = _scheduler_pkg.SchedulerService.update_daily_schedule(sched.schedule_id, updates.get("time_str"), session=self.db)
                if updated:
                    result.update({"ok": True, "schedule_id": updated.schedule_id})
                else:
                    result.update({"ok": False, "error": "update_failed"})
            except Exception as e:
                result.update({"ok": False, "error": str(e)})
        else:
            result.update({"ok": False, "error": "no_supported_update_fields"})

        return result
    def _handle_set_timezone(self, match: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        result: Dict[str, Any] = {"ok": False, "action": "set_timezone"}

        tz = None
        if isinstance(context, dict):
            tz = context.get("timezone") or context.get("tz")
            original_text = context.get("original_text") or context.get("text") or ""
        else:
            original_text = ""

        if not tz and original_text:
            import re
            m = re.search(r"(?:timezone is|time zone is|time zone to|timezone to|set(?: my)? timezone to|set timezone to|set my time zone to|i am in|i'm in|i live in)\s+([A-Za-z/_\s-]+)", original_text, re.IGNORECASE)
            if m:
                tz = m.group(1).strip()
            else:
                m2 = re.search(r"^\s*([A-Za-z]{2,}[\sA-Za-z]*)\s*$", original_text)
                if m2:
                    candidate = m2.group(1).strip()
                    if len(candidate) > 2:
                        tz = candidate

        if not tz:
            result.update({"ok": False, "error": "invalid_timezone"})
            return result

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
            tz_name = tz_raw.replace(" ", "_")

        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz_name)
        except Exception:
            result.update({"ok": False, "error": f"invalid_timezone: {tz_name}"})
            return result

        try:
            u = self.db.query(User).filter_by(user_id=user_id).first()
            if u is not None:
                u.timezone = tz_name
                self.db.add(u)
                self.db.commit()

            self.memory_manager.store_memory(user_id, "user_timezone", tz_name, category="profile", source="trigger_dispatcher")

            try:
                SchedulerService = _scheduler_pkg.SchedulerService
                active_schedules = self.db.query(Schedule).filter_by(user_id=user_id, is_active=True, schedule_type="daily").all()
                for sched in active_schedules:
                    preferred = self.memory_manager.get_memory(user_id, "preferred_lesson_time")
                    if preferred and preferred[0].get("value"):
                        time_str = preferred[0].get("value")
                    else:
                        if sched.next_send_time:
                            try:
                                local_dt = sched.next_send_time.astimezone(ZoneInfo(tz_name))
                                time_str = f"{local_dt.hour:02d}:{local_dt.minute:02d}"
                            except Exception:
                                time_str = None
                        else:
                            time_str = None

                    try:
                        updated = SchedulerService.update_daily_schedule(sched.schedule_id, time_str, session=self.db)
                        if not updated and time_str:
                            try:
                                SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=sched.lesson_id, time_str=time_str, session=self.db)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            result.update({"ok": True, "timezone": tz_name})

            try:
                conf_text = f"Okay — timezone set to {tz_name}. I'll use local time for your reminders."
                try:
                    user_lang = get_user_language(self.memory_manager, user_id)
                    if user_lang and user_lang.lower() not in ("english", "en"):
                        try:
                            conf_text = translate_text_sync(conf_text, user_lang)
                        except Exception:
                            pass
                except Exception:
                    pass

                user = self.db.query(User).filter_by(user_id=user_id).first()
                if user and getattr(user, 'external_id', None):
                    import asyncio
                    chat_id = int(user.external_id)
                    asyncio.run(_scheduler_pkg.send_message(chat_id, conf_text))
            except Exception:
                pass

            return result
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            result.update({"ok": False, "error": str(e)})
            return result

    def _handle_query_schedule(self, match: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        user_id = context.get("user_id")
        result: Dict[str, Any] = {"ok": False, "action": "query_schedule"}
        try:
            schedules = schedule_manager.get_user_schedules(user_id, session=self.db)
            try:
                user = self.db.query(User).filter_by(user_id=user_id).first()
                tz_name = getattr(user, "timezone", "UTC") if user else "UTC"
            except Exception:
                tz_name = "UTC"

            try:
                from src.services.dialogue.schedule_query_handler import build_schedule_status_response
                resp_text = build_schedule_status_response(schedules, tz_name)
            except Exception:
                resp_text = "Here are your reminders."

            try:
                user_lang = get_user_language(self.memory_manager, user_id)
                if user_lang and user_lang.lower() not in ("english", "en"):
                    try:
                        resp_text = translate_text_sync(resp_text, user_lang)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                user = self.db.query(User).filter_by(user_id=user_id).first()
                if user and getattr(user, 'external_id', None):
                    import asyncio
                    chat_id = int(user.external_id)
                    asyncio.run(_scheduler_pkg.send_message(chat_id, resp_text))
            except Exception:
                pass

            result.update({"ok": True, "note": "sent"})
            return result
        except Exception as e:
            result.update({"ok": False, "error": str(e)})
            return result

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
            # Delegate to smaller handler methods where available
            if action == "create_schedule":
                result = self._handle_create_schedule(match, context)
            elif action == "update_schedule":
                result = self._handle_update_schedule(match, context)
            elif action == "next_lesson":
                lesson_id = context.get("lesson_id")
                if not lesson_id:
                    result.update({"ok": False, "error": "missing_lesson_id"})
                else:
                    self.memory_manager.set_next_lesson(user_id, int(lesson_id))
                    result.update({"ok": True, "lesson_id": int(lesson_id)})
            elif action == "enter_rag":
                self.memory_manager.store_memory(user_id, "rag_mode", "on", category="conversation", source="trigger_dispatcher")
                result.update({"ok": True})
            elif action == "exit_rag":
                self.memory_manager.store_memory(user_id, "rag_mode", "off", category="conversation", source="trigger_dispatcher")
                result.update({"ok": True})
            elif action == "set_timezone":
                result = self._handle_set_timezone(match, context)
            elif action == "query_schedule":
                result = self._handle_query_schedule(match, context)
            else:
                result.update({"ok": False, "error": "unknown_action"})

            # Audit every dispatch
            self._audit(user_id, match.get("trigger_id"), action, {"context": context, "result": result})

        except Exception as e:
            logger.exception("Error dispatching trigger")
            result.update({"ok": False, "error": str(e)})

        return result


# module-level convenience
_dispatcher: TriggerDispatcher | None = None


def get_trigger_dispatcher(db=None, memory_manager: MemoryManager = None) -> TriggerDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TriggerDispatcher(db=db, memory_manager=memory_manager)
    return _dispatcher

