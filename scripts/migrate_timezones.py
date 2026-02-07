"""Migrate non-IANA timezone strings in users.timezone to IANA where possible.

This script will:
- Scan `users` table for timezone values that `zoneinfo.ZoneInfo` cannot resolve
- Attempt to resolve via `resolve_timezone_name` from `src.services.timezone_utils`
- Update the `users.timezone` column with the resolved IANA name and print a report

Usage:
    python -m scripts.migrate_timezones
"""
from src.models.database import SessionLocal, User
from src.services.timezone_utils import validate_timezone_name, resolve_timezone_name


def migrate():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        changed = 0
        for u in users:
            tz = getattr(u, 'timezone', None)
            if not tz:
                continue
            if validate_timezone_name(tz):
                continue
            resolved = resolve_timezone_name(tz)
            if resolved:
                print(f"Updating user {u.user_id} timezone '{tz}' -> '{resolved}'")
                u.timezone = resolved
                db.add(u)
                changed += 1
        if changed:
            db.commit()
        print(f"Done. Updated {changed} users.")
    finally:
        db.close()


if __name__ == '__main__':
    migrate()
