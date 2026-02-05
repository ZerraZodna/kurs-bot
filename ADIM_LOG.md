# Admin notification log plan

## Goal
Provide a clear plan to add an admin Telegram account name that receives bot notifications.

## Notifications to support
- GDPR daily clean performed.
- Server was offline, now online.
- New user: <Name> has arrived.
- User <Name> has left (GDPR exit, or declined to commit to lessons).

## Data/config
- Add `ADMIN_TELEGRAM_USERNAME` to `.env` (single username, without @).
- Optional future: allow multiple admins via comma‑separated list.

## Proposed behavior
1. On startup, read `ADMIN_TELEGRAM_USERNAME`.
2. Resolve the admin chat destination:
   - If the bot already has a conversation with that username, use the existing chat ID.
   - If not, send a one‑time “Please /start me to receive admin notifications.” message when possible, then cache chat ID after first interaction.
3. Route notifications to the admin chat ID.

## Events and triggers
- **GDPR daily clean performed**
  - Trigger after successful GDPR cleanup job.
- **Server was offline, now online**
  - Trigger on app start when the recovery routine detects downtime since last heartbeat.
- **New user: <Name> has arrived**
  - Trigger after user creation or first successful onboarding step.
- **User <Name> has left**
  - Trigger on GDPR delete or explicit “declined to commit” state.

## Message format (example)
- `[INFO] GDPR cleanup completed at YYYY‑MM‑DD HH:MM`.
- `[WARN] Server was offline and is now online (downtime detected).`
- `[INFO] New user joined: <Name>.`
- `[INFO] User left: <Name> (reason: GDPR exit|declined).`

## Implementation steps
1. Add env config in `src/config.py` for `ADMIN_TELEGRAM_USERNAME`.
2. Extend Telegram integration to resolve admin chat ID and cache it.
3. Add a small `admin_notifier` service with `send_admin_notification(type, payload)`.
4. Wire event hooks:
   - GDPR job completion.
   - Startup recovery/downtime detection.
   - User creation/onboarding success.
   - GDPR deletion or “declined” status.
5. Add logs for notification failures (do not crash on failure).

## Open questions
None (activity is already logged elsewhere; send via Telegram only).
