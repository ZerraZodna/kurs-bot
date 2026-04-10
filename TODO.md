# Task Progress: Implement /lesson Telegram Command

task_progress Items:
- [x] Step 1: Update src/lessons/delivery.py - Make deliver_lesson async, rename/export as handle_lesson_request with chat_id param, integrate telegram.send_message (reuse _parse_lesson_int, get_lesson_or_import, format_lesson_message, set_current_lesson)
- [x] Step 2: Update src/integrations/telegram.py - Add /lesson handling in process_telegram_batch early (parse n, call handle_lesson_request, skip LLM)
- [x] Step 3: Run npm run lint && npm run test
- [ ] Step 4: Manual test verification (send /lesson 29, /lesson in Telegram, check DB with scripts/inspect/inspect_users.py)
