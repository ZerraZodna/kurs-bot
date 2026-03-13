from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base
import logging
import sys

# Use Settings from config.py for database URL
from src.config import settings

# Ensure an empty string from env doesn't override the intended default
DEFAULT_DB = "sqlite:///./src/data/prod.db"
DATABASE_URL = settings.DATABASE_URL or DEFAULT_DB
if not isinstance(DATABASE_URL, str) or DATABASE_URL.strip() == "":
    DATABASE_URL = DEFAULT_DB

is_sqlite = isinstance(DATABASE_URL, str) and DATABASE_URL.startswith("sqlite")

# Safety: if running under pytest (or explicit test env flag), ensure we never
# point at a production DB. This prevents accidental destructive test fixtures
# from operating on prod.db.
if getattr(settings, "IS_TEST_ENV", False) or any("pytest" in str(a) for a in sys.argv):
    if "prod.db" in DATABASE_URL:
        logging.getLogger(__name__).warning(
            "Detected test run with DATABASE_URL pointing to prod.db - overriding to test.db to avoid data loss."
        )
        DATABASE_URL = "sqlite:///./src/data/test.db"
    else:
        # Ensure there's a sensible default for tests when none provided
        DATABASE_URL = DATABASE_URL or "sqlite:///./src/data/test.db"

engine = create_engine(
    DATABASE_URL,
    pool_size=10, max_overflow=20,
    connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {},
    future=True,
) if not is_sqlite else create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)

# Log/print which database URL is in use when the module is imported so
# it's visible on app startup.
logger = logging.getLogger(__name__)
try:
    print(f"🧪 Using database: {DATABASE_URL}")
    logger.info("Using database: %s", DATABASE_URL)
except Exception:
    # Best-effort logging; avoid raising during import.
    pass

# SQLite connection pragmas
if is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")

        finally:
            cursor.close()

Base = declarative_base()
