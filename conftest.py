"""
Pytest configuration for kurs-bot tests.
Central location for all test database setup and configuration.
"""

# Load .env early so its variables are available to pytest and any imported
# project modules during collection. We implement a small, dependency-free
# loader so tests do not need `python-dotenv` installed.
import os

os.environ.setdefault("IS_TEST_ENV", "1")
from pathlib import Path

import pytest


def _load_dotenv_if_present():
    repo_root = Path(__file__).resolve().parent
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    try:
        with env_path.open("r", encoding="utf8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if k and os.getenv(k) is None:
                    os.environ[k] = v
    except Exception:
        pass


_load_dotenv_if_present()
import sys
import types
from typing import Optional

# Fake Ollama for fast collection
_test_use_real = os.getenv("TEST_USE_REAL_OLLAMA")
if not _test_use_real or str(_test_use_real).strip().lower() not in ("1", "true", "yes", "y"):
    mod_name = "src.services.dialogue.ollama_client"
    if mod_name not in sys.modules:
        _fake = types.ModuleType(mod_name)

        async def _fake_call_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None) -> str:
            short = (prompt[:160] + "...") if len(prompt) > 160 else prompt
            return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

        async def _fake_stream_ollama(
            prompt: str, model: Optional[str] = None, language: Optional[str] = None, temperature=None
        ):
            short = (prompt[:160] + "...") if len(prompt) > 160 else prompt
            yield f"[MOCK_OLLAMA_STREAM] model={model or 'default'} lang={language or 'en'} text={short}"

        _fake.call_ollama = _fake_call_ollama
        _fake.stream_ollama = _fake_stream_ollama
        sys.modules[mod_name] = _fake
        # Ensure the package exposes attributes that tests may monkeypatch
        import importlib

        pkg = importlib.import_module("src.services.dialogue")
        pkg.ollama_client = _fake
        pkg.call_ollama = _fake.call_ollama


# pytest plugins (DB fixtures imported here trigger db_engine)
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.users",
    "tests.fixtures.services",
]

from src.models.database import Base


@pytest.fixture(scope="module", autouse=True)
def module_db_setup(db_engine):
    """Module-scoped DB schema creation (once per test file/module)."""
    Base.metadata.create_all(db_engine)
    yield
    # Temp DB cleaned by fixture, no drop_all needed


@pytest.fixture(scope="function", autouse=True)
def truncate_test_tables(db_engine):
    """Fast per-test cleanup: DELETE FROM key tables (100x faster than drop_all). Safe if tables missing."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    with db_engine.connect() as conn:
        for table in ["schedule", "message_log", "memory", "user"]:
            try:
                conn.execute(text(f"DELETE FROM {table}"))
            except OperationalError:
                pass  # Table not exists OK
        conn.commit()


@pytest.fixture(autouse=True)
def block_external_http():
    """Block accidental Ollama calls unless TEST_USE_REAL_OLLAMA=1."""
    if os.getenv("TEST_USE_REAL_OLLAMA"):
        yield
        return
    orig_request = None
    try:
        import httpx

        LOCAL = "localhost:11434"
        CLOUD = "ollama.com"

        def is_ollama_url(u):
            s = str(u)
            return LOCAL in s or CLOUD in s

        orig_request = httpx.request

        def blocked_request(method, url, *args, **kwargs):
            if is_ollama_url(url):
                raise RuntimeError("Blocked Ollama HTTP in tests (set TEST_USE_REAL_OLLAMA=1)")
            return orig_request(method, url, *args, **kwargs)

        httpx.request = blocked_request
    except Exception:
        pass
    yield
    try:
        import httpx

        if orig_request:
            httpx.request = orig_request
    except Exception:
        pass


def pytest_collection_modifyitems(config, items):
    serial_items = [i for i in items if i.get_closest_marker("serial")]
    other_items = [i for i in items if not i.get_closest_marker("serial")]
    items[:] = other_items + serial_items


def pytest_configure(config):
    defaults_model = "llama3.2:3b"
    overrides = {
        "OLLAMA_MODEL": os.getenv("TEST_OLLAMA_MODEL", defaults_model),
        "NON_ENGLISH_OLLAMA_MODEL": os.getenv("TEST_NON_ENGLISH_OLLAMA_MODEL", defaults_model),
    }
    changed = False
    for k, v in overrides.items():
        if v.endswith(":test"):
            v = defaults_model
        os.environ[k] = v
        changed = True
    if changed:
        try:
            import importlib

            import src.config as cfg

            importlib.reload(cfg)
            print("🔧 Test Ollama model overrides applied")
        except Exception:
            pass
