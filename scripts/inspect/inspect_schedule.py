"""Inspect a schedule row and print next_send_time details.

Usage:
    python scripts/inspect/inspect_schedule.py --schedule-id 1
    python scripts/inspect/inspect_schedule.py --user-id 4

This prints repr, isoformat, tzinfo and converts the stored value to the user's timezone for clarity.
"""

import argparse
import datetime
from zoneinfo import ZoneInfo

from src.models.database import Schedule, SessionLocal, User


def inspect_by_schedule_id(db, schedule_id):
    sched = db.query(Schedule).filter_by(schedule_id=schedule_id).first()
    if not sched:
        print(f"Schedule {schedule_id} not found")
        return
    print(f"Schedule id={sched.schedule_id} user_id={sched.user_id} schedule_type={sched.schedule_type}")
    _print_ns(sched.next_send_time, sched.user_id, db)


def inspect_by_user_id(db, user_id):
    sched = db.query(Schedule).filter_by(user_id=user_id).order_by(Schedule.created_at).first()
    if not sched:
        print(f"No schedule found for user {user_id}")
        return
    print(f"Found schedule id={sched.schedule_id} for user {user_id}")
    _print_ns(sched.next_send_time, user_id, db)


def _print_ns(ns, user_id, db):
    print("raw repr:", repr(ns))
    if ns is None:
        print("next_send_time is None")
        return
    try:
        print("isoformat:", ns.isoformat())
    except Exception as e:
        print("isoformat() failed:", e)
    print("tzinfo:", getattr(ns, "tzinfo", None))

    # Fetch user tz
    user = db.query(User).filter_by(user_id=user_id).first()
    user_tz = getattr(user, "timezone", None) if user else None
    print("user.timezone:", user_tz)

    # If naive, assume UTC for inspection (code's current behavior)
    if getattr(ns, "tzinfo", None) is None:
        print("Interpreting stored value as UTC (naive) for inspection")
        ns_assumed = ns.replace(tzinfo=datetime.timezone.utc)
    else:
        ns_assumed = ns

    try:
        if user_tz:
            local = ns_assumed.astimezone(ZoneInfo(user_tz))
            print(f"Interpreted as UTC -> local: {local.isoformat()} ({user_tz})")
        else:
            print("No user timezone available to convert to local time")
    except Exception as e:
        print("Conversion to user timezone failed:", e)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--schedule-id", type=int)
    p.add_argument("--user-id", type=int)
    args = p.parse_args()

    db = SessionLocal()
    try:
        if args.schedule_id:
            inspect_by_schedule_id(db, args.schedule_id)
        elif args.user_id:
            inspect_by_user_id(db, args.user_id)
        else:
            print("Please pass --schedule-id or --user-id")
    finally:
        db.close()
