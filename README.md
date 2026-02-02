# Kurs Bot

A chatbot/consultant with persistent memory that delivers daily lessons and interval reminders via DM channels (Telegram, Slack, SMS, Teams) and email.

## Tech Stack
- Python 3.10+
- FastAPI
- SQLAlchemy ORM
- SQLite (for prototyping) / SQL Server (production)
- Alembic (migrations)
- pytest (testing)

## Setup

1. Clone the repo and create a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   - Copy `.env.template` to `.env` and fill in your secrets (see below).

3. Initialize the database and run migrations:
   ```powershell
   alembic upgrade head
   ```

4. Run the app:
   ```powershell
   .venv\Scripts\activate
   uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
   ```

5. Expose webhook with ngrok:
   ```powershell
   ngrok http 8000
   # then set Telegram webhook to https://<ngrok-id>.ngrok.io/webhook/telegram
   ```

6. Run tests:
   ```powershell
   .\run_tests.ps1
   ```

## Development Commands

Use `cmd.py` for common development tasks:

```bash
# Database management
python cmd.py db status              # Show database status
python cmd.py db reset               # Reset dev.db (keeps 365 lessons)
python cmd.py db backup              # Create backup
python cmd.py db fresh-start         # Complete fresh start (delete + re-import)
python cmd.py db info                # Show detailed DB info

# ACIM lessons
python cmd.py import-lessons         # Import ACIM lessons from PDF

# Debugging
python cmd.py debug memory           # Debug memory extraction
python cmd.py debug schedule         # Debug schedule creation

# Production
python cmd.py init-prod              # Initialize production database
```

See [SCRIPTS_ORGANIZATION.md](SCRIPTS_ORGANIZATION.md) for full script documentation.

## Configuration (.env)
- `DATABASE_URL` - Database connection string (default: SQLite for dev)
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `SLACK_BOT_TOKEN` - Slack bot token
- `SENDGRID_API_KEY` - SendGrid API key

## Project Structure
- `src/models/database.py` - SQLAlchemy ORM models
- `src/api/app.py` - FastAPI app and webhook handler
- `src/services/` - Business logic (memory, scheduling, etc.)
- `src/integrations/` - Channel integrations (Telegram, Slack, etc.)
- `migrations/` - Alembic migration scripts
- `tests/` - Unit tests

## Purpose
Kurs Bot is designed to help users complete wellness lessons and receive reminders, with persistent memory and multi-channel support.

---