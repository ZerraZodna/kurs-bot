# TODO: Interactive Daily Practice Reminders

> **Goal:** After delivering the daily lesson, ask the user if they want practice reminders for lessons that suggest extra practice. If yes, send tailored hourly reminders (sharp on the hour) until evening. No database migration — AI extracts everything from lesson text on-demand, caches results in a new `practice_instructions` JSON column.

---

## Overview

ACIM lessons have varied practice patterns:
- **Hourly** (e.g., lesson 104: "hourly five minutes")
- **Morning & evening** (e.g., lesson 1: "morning and evening")
- **Three times daily** (e.g., lesson 31, 32)
- **Twice daily** (e.g., lesson 1, 20)
- **Single daily** (default — no extra reminders needed)

Currently the bot only delivers the daily lesson at 6:30 AM. We need to:
1. Let AI read each lesson and extract practice instructions
2. Cache results in a new `practice_instructions` column (run once, reuse)
3. After daily lesson delivery, ask the user if they want reminders
4. If yes → create hourly (or pattern-specific) reminder jobs for the rest of the day
5. Each reminder includes the key phrase + brief instruction
6. User can stop reminders with `/stop_daily_reminders`

---

## Steps

### Step 1: Add `practice_instructions` column to `lessons` table ✅

**File:** `src/models/schedule.py` (Lesson model)

Added nullable `Text` column:
```python
practice_instructions = Column(Text, nullable=True)  # JSON string
```

Migration script: `scripts/migrate_practice_instructions.py` (idempotent, safe to run multiple times).

Done: Column added to prod DB, migration is idempotent.

---

### Step 2: Create AI extraction function ✅

**File:** `src/lessons/practice_extractor.py` (new)

Create a function that:
1. Takes a `Lesson` object as input
2. Calls Ollama with a prompt that asks the AI to extract:
   - `frequency`: `"hourly"` | `"twice_daily"` | `"three_times_daily"` | `"morning_evening"` | `"single"` | `"custom"`
   - `key_phrases`: list of italicized self-talk instructions (the actual text the user should repeat)
   - `instructions`: what the user should do (e.g., "Take five minutes. Practice with eyes open.")
   - `practice_window`: e.g., `"hourly from 7:00 to 22:00"` | `"morning and evening"`
3. Returns a structured dict
4. Caller stores the dict as a JSON string in `practice_instructions`

**Prompt design:** The AI should parse the lesson content and find:
- Explicit time instructions ("hourly five minutes", "twice a day", "morning and evening")
- Italicized self-talk text (the actual phrases to repeat)
- Any duration or method instructions

The prompt should instruct the AI to return JSON with the above fields, handling cases where information is missing (use `null` or empty arrays).

---

### Step 3: Create the daily extraction check ✅

**File:** `src/lessons/practice_extractor.py` (new function) + scheduler integration

Create a function `check_and_extract_practice_instructions(lesson_id: int, session: Session) -> dict | None` that:
1. Checks if `practice_instructions` is already populated for the lesson
2. If **populated** → return cached JSON (no AI call needed)
3. If **empty/null** → call the AI extractor, store result in DB, return it

**Integration point:** This runs **1 hour before lesson delivery** (or whenever the lesson is about to be delivered). The scheduler checks this before sending the lesson.

**Why this matters:**
- First run: AI extracts, stores in DB
- Subsequent runs: instant DB lookup
- Next year, for new users: already cached, no re-processing

**No full migration needed:** We don't process all 365 lessons upfront. We process on-demand as lessons approach. By the end of the year, all lessons will be cached.

---

### Step 4: Add interactive follow-up after lesson delivery ✅

**File:** `src/scheduler/execution.py` (modify `_execute_lesson_schedule`)

After delivering the daily lesson, check if the lesson has `practice_instructions` with extra practice (frequency != "single"). If yes:

1. Store a **pending state** in user memories:
   ```
   key: "practice_reminder_pending"
   value: lesson_id
   ttl: 30 minutes
   ```

2. Send the user a message:
   ```
   This lesson suggests practicing [frequency].
   Would you like me to send you reminders throughout the day? (yes/no)
   ```

3. The dialogue engine needs to detect this pending state and handle "yes"/"no" responses appropriately.

**Dialogue engine integration:** Modify `_detect_context_type` in `dialogue_engine.py` to check for `practice_reminder_pending` memory and route accordingly. When user responds "yes" or "no", create or skip reminder jobs.

---

### Step 5: Create reminder jobs ✅

**File:** `src/scheduler/reminder_manager.py` (new)

Create a manager for practice reminders that:
1. Takes lesson `practice_instructions` + user preferences
2. Determines reminder times based on frequency:
   - **hourly**: every hour from next full hour until 22:00
   - **twice_daily**: morning + evening (use user's preferred lesson time as reference, or default 9:00 + 18:00)
   - **morning_evening**: same as twice_daily
   - **three_times_daily**: morning, afternoon, evening (e.g., 9:00, 14:00, 19:00)
   - **custom**: use the `practice_window` from AI extraction
3. Creates **one-time reminder schedules** in the DB for each reminder time
4. Each reminder message includes:
   - Time indicator (🕐)
   - Key phrase (from `key_phrases`)
   - Brief instruction (from `instructions`)

Example reminder:
```
🕐 Time to practice.

"I seek but what belongs to me in truth.
God's gifts of joy and peace are all I want."

Take five minutes. Find a quiet moment and repeat the idea slowly.
```

**Schedule type:** Use `one_time_reminder` (already exists). Store reminder message in memory with TTL so it's sent and then auto-expired.

---

### Step 6: Handle user "yes"/"no" response ✅

**File:** `src/services/dialogue_engine.py` (modify)

When user responds to the practice reminder prompt:
1. Check `practice_reminder_pending` memory
2. If "yes" → call `reminder_manager.create_reminders(lesson_id, user_id)`
3. If "no" → clear pending memory, send confirmation
4. Clear `practice_reminder_pending` memory in both cases

**Message examples:**
- Yes: "Great! I'll send you reminders at the top of each hour until 10 PM. Each will include today's key phrase and a brief instruction."
- No: "No problem. You can always ask me to send reminders later with 'start reminders'."

---

### Step 7: Add `/stop_daily_reminders` command ✅

**File:** `src/functions/handlers/schedule.py` (add handler) + function registry

Add a new command/function `stop_daily_reminders` that:
1. Finds all active one-time reminder schedules for the user
2. Deactivates them
3. Sends confirmation: "Daily practice reminders stopped for today."

**Also handle natural language:** Detect "stop reminders" or "no more reminders" in the dialogue engine and route to the same handler.

---

### Step 8: Add user preference for evening cutoff ✅

**File:** `src/memories/constants.py` + `src/models/user.py` or memory store

Add a new memory key: `PRACTICE_REMINDER_EVENING_CUTOFF` (default: "22:00")

Allow user to set via:
- "Change my reminder cutoff to 9 PM"
- `/set_reminder_cutoff 21:00`

The reminder manager reads this preference when creating reminder jobs.

---

### Step 9: Testing ✅

**Files:** `tests/unit/test_practice_reminders.py` (new)

Test:
1. AI extraction produces valid JSON for sample lessons
2. Reminder jobs are created correctly for different frequencies
3. User "yes"/"no" flow works end-to-end
4. `/stop_daily_reminders` cancels active reminders
5. Cached `practice_instructions` are reused (no redundant AI calls)
6. Evening cutoff preference is respected

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/models/schedule.py` | Added `practice_instructions` column to Lesson |
| `src/lessons/practice_extractor.py` | **NEW** — AI extraction + on-demand check |
| `src/scheduler/reminder_manager.py` | **NEW** — create/manage reminder jobs |
| `src/scheduler/execution.py` | Added `_maybe_ask_practice_reminders` follow-up |
| `src/services/dialogue_engine.py` | Added practice reminder response handling + stop command |
| `src/memories/constants.py` | Added 3 new memory keys |
| `scripts/migrate_practice_instructions.py` | **NEW** — idempotent DB migration |
| `tests/unit/scheduler/test_practice_reminders.py` | **NEW** — 15 tests |

---

## Design Decisions

1. **No upfront migration** — Process lessons on-demand as they approach. By end of year, all cached.
2. **AI extracts from text** — No hardcoded rules. AI finds italicized phrases, time instructions, etc.
3. **Hourly = sharp on the hour** — If lesson says "hourly", reminders at 7:00, 8:00, 9:00...
4. **Evening cutoff default 22:00** — User-configurable via memory/preferences.
5. **`/stop_daily_reminders` = stop for today only** — Next day, the bot asks again after delivering the lesson.
6. **Reminders use existing `one_time_reminder` schedule type** — No new schedule types needed.
7. **Cached results persist across years** — `practice_instructions` column stores results permanently.

---

## Design Notes (Decisions)

- **AI extraction prompt** — Stored inline in the extractor function, not in `prompt_templates`. It's implementation detail, not user-facing.
- **No batching** — Extract one lesson at a time. On-demand means we process ~1 lesson/day anyway. Batching adds complexity for negligible gain.
- **AI failure fallback** — If extraction fails or returns invalid JSON, default to `"single"` — no extra reminders. The lesson still delivers normally.
- **No admin re-extract command** — If needed, we can run the extractor manually via script. Not worth a user-facing command.

## Post-Implementation Notes

- **Session management**: All DB sessions use `with get_session()` context manager (AGENTS.md compliant).
- **`/stop_daily_reminders`** only stops practice reminders (ones with `lesson_id`), not general one-time reminders.
- **Ruff**: All checks pass (`ruff check src/ tests/` — 0 errors).
- **Tests**: 267 passed, 1 skipped, 0 failed.
- **Dead code removed**: `_get_next_full_hour()` removed (unused). `import re` moved to top of file.
- **Quote style**: All strings use double quotes per ruff Q000 rule.
- **Export**: `check_and_extract_practice_instructions` added to `src/lessons/__init__.py` `__all__`. {
