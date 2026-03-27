# Database Guide (AI Agent)

## Database Files
| Database | File Path | Purpose |
|----------|-----------|---------|
| Production | src/data/prod.db | Live users |
| Development | src/data/dev.db | Testing |
| Test | src/data/test.db | pytest |

## Tables
- users
- memories
- message_logs
- schedules
- lessons
- unsubscribes
- consent_logs
- gdpr_requests
- gdpr_audit_logs
- gdpr_verifications
- batch_locks
- job_states
- prompt_templates

## Schema
See src/models/database.py (Base model and imports).

## Management Notes
- Edit .env DATABASE_URL to switch DBs (e.g., sqlite:///./src/data/prod.db).
- Migrations: alembic.ini and migrations/ directory.
- Init: Base.metadata.create_all(bind=engine) in src/models/database.py.
