**Migration: Store UTC datetimes as ISO8601 strings**

This document describes a safe, reversible plan to migrate schedule-related datetimes to an ISO8601 text representation in the database so timezone information is preserved in SQLite (and remains portable to other DBs).

**Goal**: ensure `Schedule.next_send_time` (and any other datetime columns that must be timezone-aware) are persisted and returned as timezone-aware datetimes by the application, even when the DB driver returns naive values.

**Why**:
- SQLite and some drivers can return naive datetimes (no tzinfo), which makes it ambiguous whether stored values are UTC or local.
- Storing UTC as ISO8601 (e.g. `2026-02-07T12:10:00+00:00`) makes the intent explicit and is easy to inspect and interoperate with other tools.

**High-level plan**
- Add a SQLAlchemy `TypeDecorator` that serializes tz-aware datetimes to UTC ISO8601 strings on write and deserializes them back into `datetime` with `tzinfo=UTC` on read.
- Replace `Schedule.next_send_time` column type in the model to use this new type (column remains `TEXT` at DB level).
- Add a migration script to convert existing rows to ISO8601 strings (assume naive datetimes are UTC unless `users.timezone` indicates otherwise).
- Run tests and update any tests that assert naive vs aware behavior.
- Deploy: take DB backup, run migration script, restart services.

**Files to add / change**
- **Add**: `src/services/db_types.py` — contains `AwareDateTimeString` (TypeDecorator)
- **Edit**: `src/models/database.py` — change `Schedule.next_send_time` to use `AwareDateTimeString()`
- **Edit**: `src/services/scheduler/manager.py` — likely no change needed, but keep `to_utc()` calls; verify behavior after tests
- **Add**: `scripts/migrate_next_send_to_iso8601.py` — idempotent migration script that updates existing rows
- **Add**: tests or update existing tests under `tests/` that rely on `next_send_time` to assert tz-aware datetimes

**Implementation details**
- TypeDecorator (recommended): `AwareDateTimeString`
  - `process_bind_param(value, dialect)`:
    - If `value` is None -> return None
    - If `value.tzinfo` is None -> assume UTC or call `to_utc` depending on policy; set tzinfo to UTC
    - Convert to UTC and return `value.astimezone(timezone.utc).isoformat()`
  - `process_result_value(value, dialect)`:
    - If `value` is None -> return None
    - Return `datetime.fromisoformat(value)` (results in tz-aware datetime if string has offset)

- Model change:
  - Replace `next_send_time = Column(DateTime(timezone=True))` with `next_send_time = Column(AwareDateTimeString(), nullable=True)`

**Migration script behavior**
- Connect to DB and iterate schedules where `next_send_time` is not null.
- For each row:
  - If value is already a string that looks like an ISO8601 with offset -> skip
  - If value is a datetime object (depends on SQLAlchemy driver) and `tzinfo` is None:
    - If `users.timezone` exists and is a valid IANA name, interpret the naive value as local in that timezone and convert to UTC using `parse_local_time_to_utc` or `to_utc` appropriately.
    - Otherwise assume the naive value is already UTC (legacy assumption)
  - Update row with ISO8601 UTC string via the new TypeDecorator (or directly write `dt.astimezone(timezone.utc).isoformat()`)
- Commit in batches; log summary of updated rows and any failures.

**Safety / rollback**
- Always back up DB first. Example SQLite copy:

```powershell
copy data/db.sqlite3 data/db.sqlite3.bak
```

- Migration script is idempotent: it should not change rows that are already ISO8601 with UTC offset.
- To rollback: restore DB from the backup.

**Testing**
- Run full test suite after applying the TypeDecorator and model change. Expect to update tests that compare `tzinfo is None` or rely on naive datetimes.
- Add a unit test that:
  - Writes a schedule with a tz-aware `datetime` -> read back and assert `tzinfo` is `timezone.utc` and `isoformat()` includes `+00:00`.
  - Writes a schedule with naive `datetime` (assumed UTC) -> assert normalized result is UTC-aware.

**Deployment steps**
1. `git checkout -b feat/iso8601-next-send`
2. Implement `src/services/db_types.py` and update `src/models/database.py`.
3. Commit and run `pytest` locally; update failing tests.
4. Create DB backup.
5. Run migration script:

```powershell
$env:PYTHONPATH = 'D:\dev\kurs-bot'
python scripts/migrate_next_send_to_iso8601.py
```

6. Restart service (e.g., `uvicorn`) and monitor logs.
7. Verify a few schedule rows with `scripts/inspect_schedule.py`.

**Notes & decisions**
- Policy for naive datetimes: choose either (A) assume naive = UTC (less breaking) or (B) reject naive and require callers to pass tz-aware datetimes (stricter). The migration script must follow the chosen policy.
- ISO8601 strings are human-readable and portable; epoch integers are more compact but less readable. I recommend ISO8601 for this project.

**Follow-ups (optional enhancements)**
- Add database-level invariant checks (if using Postgres) to ensure values are stored with timezone.
- Add a small admin endpoint to list schedules with canonical ISO strings for debugging.
- Expand `resolve_timezone_name()` mapping to a more complete Windows→IANA mapping.

**Contact**
If you want, I can implement the `AwareDateTimeString` TypeDecorator, update the model, add the migration script `scripts/migrate_next_send_to_iso8601.py`, and run the test suite — tell me to proceed and which naive-datetime policy you prefer (assume UTC or reject).