# Admin notifications (design)

Purpose
- Provide a concise spec for in-repo admin notifications sent via Telegram.
- Focused on implementation details, configuration, and events — not user-facing docs.

Configuration
- `ADMIN_TELEGRAM_USERNAME` (string) — username (without `@`) configured via `.env` or environment. Default empty.
- Admin chat id is discovered at webhook time and persisted in the database via the `job_state` table.

Behavior
- On incoming Telegram messages the app checks whether the message sender's username
  matches `ADMIN_TELEGRAM_USERNAME`. If so, it records the chat id for future notifications.
- Notifications are sent best-effort and do not crash the app on failure. Failures are logged.

Events to notify (examples)
- GDPR daily cleanup completed.
- Server downtime recovered (offline -> online detection).
- New user joined (first known interaction).
- User left (GDPR deletion or explicit opt-out/decline).

Message format (examples)
- `[INFO] GDPR cleanup completed at YYYY-MM-DD HH:MM`.
- `[WARN] Server was offline and is now online (downtime detected).`.
- `[INFO] New user joined: <Name>.`.
- `[INFO] User left: <Name> (reason: GDPR exit|declined).`.

Implementation notes / pointers
- Config: `src/config.py` exposes `ADMIN_TELEGRAM_USERNAME`.
- Persistence: `src/services/job_state.py` provides `get_state`/`set_state` used to store the admin chat id.
- Notifier: `src/services/admin_notifier.py` implements `set_admin_chat_id`, `get_admin_chat_id`, and `send_admin_notification(message)`.
- Telegram integration: `src/integrations/telegram.py` provides `send_message(chat_id, text)` used by the notifier.
- Webhook: `src/api/app.py` sets the admin chat id when the configured username messages the bot.
- Consumers: notifier is invoked by downtime monitor, GDPR flows and onboarding/user management.

Robustness
- Do not fail startup or critical flows if notifications cannot be delivered.
- Log failures for operator visibility and retry where appropriate in background jobs.

Next actions
- Keep this doc in `docs/` for discoverability; remove the root-level note once satisfied.
- Optionally expand with examples for multi-admin support and admin onboarding UX (e.g. one-time "please /start" prompt).
