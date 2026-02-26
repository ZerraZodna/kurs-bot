# Lesson Delivery Flow

This document describes how lessons are tracked, confirmed, and delivered
after onboarding and on subsequent days. It is the authoritative reference
for the lesson state machine.

## Key State Variables

Two values are stored per user in a consolidated `lesson_state` JSON memory
(key: `lesson_state`, category: `progress`):

| Field | Set by | Meaning |
|---|---|---|
| `current_lesson` | Onboarding or user report | The lesson the user says they are working on |
| `last_sent_lesson_id` | Bot after delivering a lesson | The last lesson the bot actually sent to the user |

**After onboarding**: `current_lesson = N`, `last_sent_lesson_id = None`.
No lesson is delivered during onboarding itself.

## State Decision Logic

`src/lessons/state.py` → `compute_current_lesson_state(mm, user_id, today=)`:

| Condition | Result |
|---|---|
| `current_lesson` is set, `last_sent` is `None` | `need_confirmation = True` — ask user before delivering |
| `last_sent` is set, `updated_at.date() < today` | `advanced_by_day = True`, `lesson_id = last_sent + 1` |
| `last_sent` is set, same day | `lesson_id = last_sent`, no advance |
| Nothing set | Fallback to lesson 1 |

`src/lessons/state_flow.py` → `determine_lesson_action()` wraps this into
actionable decisions: `"send"`, `"confirm"`, or `"wait"`.

## Day-by-Day Flow (Example: User onboards with lesson 17)

### Day 0 — Onboarding
- User says "I'm on lesson 17"
- `set_current_lesson(mm, user_id, 17)` → `current_lesson=17, last_sent=None`
- A daily schedule is created (e.g., 09:00)
- **No lesson is delivered**

### Day 1 — Scheduler fires
1. `src/scheduler/execution.py` → `_execute_lesson_schedule()`
2. Checks `last_sent_lesson_id` → `None`
3. Calls `_handle_no_last_sent_execution()` → reads `current_lesson=17`
4. Sends **confirmation prompt**: "Quick check-in: are you still on lesson 17?"
5. Stores pending confirmation: `{lesson_id: 17, next_lesson_id: 18}`

### Day 1 — User confirms "yes"
1. `src/services/dialogue/reminder_handler.py` → `handle_lesson_confirmation()`
2. Reads pending confirmation → `{lesson_id: 17, next_lesson_id: 18}`
3. Classifies "yes" via `_semantic_yes_no()` (see Trigger Dependencies below)
4. Marks lesson 17 as completed
5. Delivers lesson 18
6. Sets `last_sent_lesson_id = 18`
7. Resolves pending confirmation

### Day 2 — Scheduler fires
1. `compute_current_lesson_state()` sees `last_sent=18`, `updated_at` is yesterday
2. Returns `advanced_by_day=True`, `lesson_id=19`, `previous_lesson_id=18`
3. Scheduler sends confirmation prompt for lesson 18
4. User confirms → gets lesson 19, `last_sent=19`

## Trigger Dependencies for Confirmation

`_semantic_yes_no()` in `src/services/dialogue/reminder_handler.py` classifies
user responses using trigger embeddings:

- Computes embedding of user text via sentence-transformers
- Matches against `trigger_embeddings` table for `action_type = confirm_yes` or `confirm_no`
- Returns `(is_yes, is_no)` based on cosine similarity vs threshold (0.55)

**CRITICAL**: The `trigger_embeddings` table MUST contain `confirm_yes` and
`confirm_no` entries. Without them, `_semantic_yes_no` returns `(False, False)`
for ALL inputs and the confirmation flow silently breaks (returns `None`).

These triggers are defined in `src/triggers/trigger_matcher.py` → `STARTER` list
and must be present in `scripts/ci_trigger_data.py`. See `docs/EMBEDDINGS_TRIGGERS.md`
for the full trigger pipeline.

## Key Source Files

| File | Role |
|---|---|
| `src/lessons/state.py` | `get_lesson_state`, `set_current_lesson`, `set_last_sent_lesson_id`, `compute_current_lesson_state` |
| `src/lessons/state_flow.py` | `determine_lesson_action` (send/confirm/wait), `apply_reported_progress` |
| `src/lessons/advance.py` | `maybe_send_next_lesson` — greeting-triggered lesson delivery |
| `src/scheduler/execution.py` | `_execute_lesson_schedule`, `_handle_no_last_sent_execution` |
| `src/services/dialogue/reminder_handler.py` | `handle_lesson_confirmation`, `_semantic_yes_no` |
| `src/scheduler/memory_helpers.py` | `get_pending_confirmation`, `set_pending_confirmation` |
| `src/language/onboarding_prompts.py` | `get_lesson_confirmation_prompt` (template text) |

## Test Coverage

| Test File | What it covers |
|---|---|
| `tests/unit/lessons/test_next_day_confirmation.py` | Full two-day flow, confirmation prompts, auto-advance preference |
| `tests/unit/triggers/test_ci_trigger_data_completeness.py` | CI trigger data matches STARTER, `_semantic_yes_no` works with real embeddings |
| `tests/e2e/test_onboarding_e2e.py` | Onboarding → scheduler execution → confirmation prompt |
| `tests/e2e/test_onboarding_flow_e2e.py` | Full onboarding conversation → daily schedule creation |

## Known Issues & Gotchas

1. **Stale `ci_trigger_data.py`**: If STARTER is updated but `ci_trigger_data.py`
   is not regenerated, tests will have missing triggers. The completeness test
   catches this. Regenerate with:
   ```bash
   ALLOW_EXPORT_PROD=1 .venv/bin/python scripts/export_trigger_embeddings.py \
     --from-starter --out scripts/ci_trigger_data.py
   ```

2. **TriggerMatcher singleton caching**: The matcher caches triggers for
   `TRIGGER_MATCHER_REFRESH_SECS`. In tests, call `refresh_trigger_matcher_cache()`
   to force reload from the test DB.

3. **Production DB sync**: The prod DB on AWS may not automatically get new
   triggers when STARTER is updated. A startup failsafe is needed (see TODO.md).
