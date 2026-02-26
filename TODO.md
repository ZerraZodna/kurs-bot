# TODO: Next Day After Onboarding — Session Summary & Next Steps

## Completed ✅

### 1. Verify `TestSemanticYesNoWithRealTriggers` tests pass ✅
- **Fix**: Added simpler phrases ("yes", "no", "ja", "nei") to `confirm_yes_phrases`
  and `confirm_no_phrases` in `src/triggers/trigger_matcher.py` so the semantic
  matcher can classify short inputs reliably.
- STARTER grew from 123 → 127 entries.
- Regenerated `scripts/ci_trigger_data.py` via:
  `EMBEDDING_BACKEND=local ALLOW_EXPORT_PROD=1 .venv/bin/python scripts/export_trigger_embeddings.py --from-starter --out scripts/ci_trigger_data.py`
- All 9 tests in `test_ci_trigger_data_completeness.py` now pass (including the
  4 `_semantic_yes_no` tests) in ~4 seconds.
- All 23 trigger tests pass.

### 2. Production DB trigger sync failsafe ✅
- **Implemented** a startup check in `src/api/app.py` lifespan that:
  1. Counts rows in `trigger_embeddings`
  2. Compares against `len(STARTER)`
  3. If count ≠ len(STARTER), truncates and re-seeds from `scripts/ci_trigger_data.py`
  4. Logs a warning when re-seeding occurs, or an info message when counts match
  5. Skipped in test environments (`IS_TEST_ENV`)
- **Also fixed** `scripts/ci_seed_triggers.py` to TRUNCATE existing rows before
  inserting, so `npm run seed_triggers` is safe for repeated production use
  (no duplicate rows).
- `npm run seed_triggers` is kept as a manual failsafe but the automatic startup
  check means it should rarely be needed.

## Files Changed
- `src/triggers/trigger_matcher.py` — Added "yes", "no", "ja", "nei" to confirm phrases
- `scripts/ci_trigger_data.py` — Regenerated (127 entries, was 123)
- `src/api/app.py` — Added trigger embeddings sync failsafe in lifespan
- `scripts/ci_seed_triggers.py` — Added TRUNCATE before re-insert
