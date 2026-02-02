# Database Management Guide

## Database Files

The project uses **three separate SQLite databases**:

| Database | File | Purpose | When to Use |
|----------|------|---------|-------------|
| **Production** | `src/data/prod.db` | Live data from real users | When running the bot for actual users |
| **Development** | `src/data/dev.db` | Manual testing and development | When testing features manually |
| **Test** | `src/data/test.db` | Automated pytest tests | Automatically used by pytest |

## Quick Start

### 1. Initialize Production Database

```bash
# Create a clean production database
python init_prod_db.py

# Update your .env file
DATABASE_URL=sqlite:///./src/data/prod.db
```

### 2. Restart Your Server

```bash
# Stop uvicorn (Ctrl+C in the uvicorn terminal)
# Then restart:
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

### 3. Verify It's Working

Check the uvicorn logs when you send a Telegram message - you should see:
- Database writes going to `prod.db`
- No test data from `dev.db`

## Database Operations

### Switch Databases

Edit `.env` and change `DATABASE_URL`:

```bash
# Production (clean data)
DATABASE_URL=sqlite:///./src/data/prod.db

# Development (test data, experiments)
DATABASE_URL=sqlite:///./src/data/dev.db
```

### Reset Production Database

```bash
# This will backup existing prod.db and create fresh one
python init_prod_db.py
```

### Clean Development Database

```bash
# Delete and recreate dev.db
rm src/data/dev.db
python -c "import os; os.environ['DATABASE_URL']='sqlite:///./src/data/dev.db'; from src.models.database import init_db; init_db()"
```

### Run Tests (Automatic Isolation)

```bash
# Tests automatically use test.db (configured in conftest.py)
pytest tests/ -v

# test.db is created/reset automatically
# Your prod.db and dev.db remain untouched
```

## Database Schema

All databases use the same schema defined in `src/models/database.py`:

- **users** - User profiles and contact info
- **memories** - User context, preferences, goals
- **message_logs** - Conversation history
- **schedules** - Lesson scheduling
- **lessons** - Lesson content
- **unsubscribes** - Opt-out tracking

## Backup Production Data

```bash
# Manual backup
cp src/data/prod.db backups/prod_$(date +%Y%m%d).db

# Or use the init script which auto-backs up before recreating
```

## Migration to SQL Server (Future)

When ready for production scale, update `DATABASE_URL`:

```bash
# SQL Server connection string
DATABASE_URL=mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+17+for+SQL+Server
```

The code already supports SQL Server - just change the connection string.

## Troubleshooting

### "Database is locked" errors

SQLite has concurrency limitations. If you see this:
1. Close any database browser tools
2. Restart uvicorn
3. Consider migrating to SQL Server for production

### Test data in production

If you accidentally ran the bot with `dev.db`:
1. Run `python init_prod_db.py` to create clean `prod.db`
2. Update `.env` to use `prod.db`
3. Restart uvicorn

### Lost data after tests

Tests use separate `test.db` - your production and dev databases are safe. The `conftest.py` file ensures test isolation.
