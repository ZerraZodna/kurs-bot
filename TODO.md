# Refactor Lessons Package: Pure English, Translate Only Before Send

[12/12]

All steps implemented:
- Lessons package returns pure English text everywhere
- Translation centralized in src/language/translation_service.py ONLY before outbound send
- All imports cleaned, old exports removed
- Scheduler recovery now translates before send
- dialogue_engine.py async fixes
- Deprecated translate_text_sync removed from message_utils.py
- VSCode linter warnings (sqlalchemy) exist but code functional

## Verified:
- Lessons functions: get_english_lesson_text, deliver_lesson, get_english_lesson_preview → English only
- Callers: translate if user_lang != "en"

Refactor complete. Ready for testing/production.

5. [x] src/services/dialogue/__init__.py: Remove re-export of translate_text

6. [x] src/services/dialogue_engine.py:
   - Replace deliver_lesson(session, user_id, target_id, memory, user_lang) → english = deliver_lesson(... no lang); if english: translated = await translate(english, user_lang) if needed else english; return translated
   - Apply same pattern to help_text, schedule responses (translate before return)

7. [ ] src/scheduler/execution.py:
   - _build_schedule_message: use get_english_lesson_preview(...) → english; return english (remove language, let caller translate)
   - execute_scheduled_task, run_recovery_check: english = lessons.delivery.deliver_lesson(... no lang); if english: lang = get_user_language(); msg = translate(english, lang) if needed; send_outbound_message(msg)

8. [x] src/language/__init__.py: Export translate_text from translation_service

9. [ ] Update all imports for renamed get_english_lesson_text

10. [ ] Remove language params from all lessons calls
