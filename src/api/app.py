from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.memories import MemoryManager
from src.services.maintenance import nightly_memory_purge
from src.middleware.consent import ConsentMiddleware
from src.middleware.api_key_auth import ApiKeyAuthMiddleware
from src.middleware.logging_redaction import apply_logging_redaction
from src.services.security_checks import verify_secrets_config
from src.models.database import SessionLocal, Lesson, Base, engine
from src.config import settings
from src.services.downtime_monitor import run_downtime_monitor
from src.scheduler import SchedulerService
from src.api.dialogue_routes import router as dialogue_router
from src.api.gdpr_routes import router as gdpr_router
from src.api.telegram_routes import router as telegram_router
from src.integrations.telegram_polling import start_polling_task
import threading
import asyncio
from urllib.parse import urlparse
from pathlib import Path
import logging
import httpx
from src.services.ollama_online_test import run_ollama_checks

def ensure_lessons_imported():
    """Auto-import lessons from PDF if database is empty."""
    try:
        # Ensure tables exist first
        Base.metadata.create_all(bind=engine)
        
        with SessionLocal() as session:
            count = session.query(Lesson).count()
            if count > 0:
                logging.info(f"Database already contains {count} lessons, skipping import")
                return
            
            # No lessons found, run import
            pdf_path = Path(__file__).resolve().parents[2] / "src" / "data" / "Sparkly ACIM lessons-extracted.pdf"
            if not pdf_path.exists():
                logging.warning(f"PDF not found at {pdf_path}, cannot auto-import lessons")
                return
            
            logging.info(f"Auto-importing lessons from {pdf_path}...")
            
            # Import the importer module
            from src.lessons import extract_formatted_text, parse_lessons_from_text, import_to_db
            
            text = extract_formatted_text(pdf_path)
            lessons = parse_lessons_from_text(text)
            
            if not lessons:
                logging.warning("No lessons found in PDF")
                return
            
            added = import_to_db(lessons, clear=False, limit=None)
            logging.info(f"✅ Auto-imported {added} lessons from PDF")
            
    except Exception as e:
        logging.exception(f"Failed to auto-import lessons: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-import lessons if database is empty
    ensure_lessons_imported()
    
    # Start background threads unless running in explicit test context
    if not getattr(settings, "IS_TEST_ENV", False):
        t = threading.Thread(target=nightly_memory_purge, daemon=True)
        t.start()

        t2 = threading.Thread(target=run_downtime_monitor, daemon=True)
        t2.start()
        
        # Start Telegram long-polling if enabled
        polling_task = start_polling_task()
    else:
        logging.info("Background threads disabled in test environment")
        polling_task = None

    # Ensure APScheduler is explicitly initialized at application startup
    try:
        SchedulerService.init_scheduler()
    except Exception:
        # Don't let scheduler initialization block app startup; log and continue
        logging.exception("Could not initialize scheduler at startup")

    # Startup info and health checks
    # Configure logging - respect uvicorn's log level if set
    # Uvicorn sets its error logger to DEBUG when --log-level debug is used
    uvicorn_error = logging.getLogger("uvicorn.error")
    is_debug = uvicorn_error.level == logging.DEBUG or uvicorn_error.getEffectiveLevel() == logging.DEBUG
    
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Uvicorn has configured logging, set appropriate level
        target_level = logging.DEBUG if is_debug else logging.INFO
        root_logger.setLevel(target_level)
        for handler in root_logger.handlers:
            handler.setLevel(target_level)
    else:
        # No handlers configured yet, set up basic logging
        logging.basicConfig(
            level=logging.DEBUG if is_debug else logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
    apply_logging_redaction()
    verify_secrets_config()
    # Ensure embedding backend requirements in production: fail-fast if
    # EMBEDDING_BACKEND=local is expected to use real embeddings but the
    # sentence-transformers package is not installed. CI/test runs should set
    # TEST_USE_REAL_OLLAMA=False so this check is skipped there.
    try:
        embedding_backend = getattr(settings, "EMBEDDING_BACKEND", "local")
        test_real = getattr(settings, "TEST_USE_REAL_OLLAMA", True)
        if str(embedding_backend).lower() == "local" and bool(test_real):
            try:
                import sentence_transformers  # type: ignore
            except Exception:
                raise RuntimeError("EMBEDDING_BACKEND=local requires sentence-transformers")
    except Exception:
        # Re-raise to stop startup; caller/lifespan will log the exception.
        raise
    # Helper functions for Ollama health checks and model discovery
    def _strip_api(path: str) -> str:
        try:
            return path.rsplit("/api", 1)[0] if "/api" in path else path
        except Exception:
            return path

    def _is_cloud_host_url(base: str) -> bool:
        try:
            hostname = urlparse(base).hostname or ""
            return "ollama.com" in hostname.lower()
        except Exception:
            return False

    def _probe_tags(base: str):
        try:
            return httpx.get(f"{base}/api/tags", timeout=2.0)
        except Exception as e:
            logging.warning(f"Ollama AI server not reachable at {base}: {e}")
            return None

    def _tags_contain_model(tags_resp, rag_model: str) -> bool:
        try:
            if tags_resp is None or tags_resp.status_code != 200:
                return False
            data = tags_resp.json()
            if isinstance(data, list):
                for item in data:
                    name = item.get("name") if isinstance(item, dict) else item
                    if name and str(name).lower() == str(rag_model).lower():
                        return True
        except Exception:
            logging.exception("Failed to inspect /api/tags response")
        return False

    def _attempt_generate_ping(base: str, rag_model: str) -> bool:
        try:
            ping = httpx.post(
                f"{base}/api/generate",
                json={"model": rag_model, "prompt": "ping", "stream": False},
                timeout=3.0,
            )
            logging.info("/api/generate ping returned %s at %s", ping.status_code, base)
            return ping.status_code == 200
        except Exception:
            logging.exception("/api/generate ping failed at %s", base)
            return False
    # Consolidated Ollama availability and model checks (refactored).
    try:
        any_ok, diagnostics = run_ollama_checks(settings)
        if not any_ok:
            logging.error("Ollama AI server is NOT reachable at configured endpoints (checked preferred endpoints)")
            for e in diagnostics:
                logging.error("Diag: %s", str(e))
        else:
            logging.info("Ollama checks passed")
            logging.debug("Ollama diagnostics: %s", diagnostics)
    except Exception:
        logging.exception("Error while running Ollama checks")

    # If embedding backend uses Ollama, explicitly confirm local Ollama is present
    embedding_backend = getattr(settings, "EMBEDDING_BACKEND", "local")
    if str(embedding_backend).lower() == "ollama":
        local = getattr(settings, "LOCAL_OLLAMA_URL", None)
        if local:
            b = local
            if "/api" in b:
                b = b.rsplit("/api", 1)[0]
            try:
                logging.info(f"Checking local Ollama for embeddings at {b}")
                resp = httpx.get(f"{b}/api/tags", timeout=2.0)
                if resp.status_code == 200:
                    logging.info(f"Local Ollama available for embeddings at {b}")
                else:
                    logging.error(f"Local Ollama responded {resp.status_code} at {b}; embeddings may fail")
            except Exception as e:
                logging.error(f"Local Ollama for embeddings not reachable at {b}: {e}")
        else:
            logging.error("Embedding backend is set to 'ollama' but LOCAL_OLLAMA_URL is not configured")

    yield

    # Shutdown: cancel Telegram polling task if running
    if polling_task:
        logging.info("[lifespan] Cancelling Telegram polling task...")
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.exception(f"[lifespan] Error during polling task cancellation: {e}")


app = FastAPI(lifespan=lifespan)

# Allow CORS for the development web UI so browser preflight (OPTIONS)
# requests succeed when the frontend hits the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(ConsentMiddleware)
app.add_middleware(ApiKeyAuthMiddleware)

# Include dialogue routes with context-aware endpoints
app.include_router(dialogue_router)
app.include_router(gdpr_router)
app.include_router(telegram_router)

# Dev Web UI (serve static client and proxy to DialogueEngine) when enabled
DEV_WEB = getattr(settings, "DEV_WEB_CLIENT", False)

# Compute project-relative static path for visibility in logs/debugging
static_path = Path(__file__).resolve().parents[2] / "static" / "dev_web_client"
logging.debug(f"settings.DEV_WEB_CLIENT={getattr(settings, 'DEV_WEB_CLIENT', None)}")
logging.debug(f"computed static_path={static_path} exists={static_path.exists()}")

if DEV_WEB:
    logging.debug("DEV_WEB is True — mounting dev static and router")
    from fastapi.staticfiles import StaticFiles
    from src.api.dev_web_client import router as dev_router

    # Mount static files under /dev/static using project-relative path
    static_dir = str(static_path)
    app.mount("/dev/static", StaticFiles(directory=static_dir), name="dev_static")
    app.include_router(dev_router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


# `nightly_memory_purge` moved to `src/services/maintenance.py`.
# Telegram webhook and batch processing moved to `src/api/telegram_routes.py`.
# Startup handled by lifespan
