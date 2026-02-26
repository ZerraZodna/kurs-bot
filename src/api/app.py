from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.memories import MemoryManager
from src.services.maintenance import nightly_memory_purge
from src.middleware.consent import ConsentMiddleware
from src.middleware.api_key_auth import ApiKeyAuthMiddleware
from src.middleware.logging_redaction import apply_logging_redaction
from src.services.security_checks import verify_secrets_config
from src.models.database import SessionLocal, User, MessageLog, BatchLock
from src.config import settings
from src.integrations.telegram import TelegramHandler, send_message, send_message_streaming
from src.services.dialogue_engine import DialogueEngine
from src.services.admin_notifier import set_admin_chat_id, send_admin_notification
from src.services.traffic_tracker import record_traffic_event
from src.services.downtime_monitor import run_downtime_monitor
from src.scheduler import SchedulerService
from src.api.dialogue_routes import router as dialogue_router
from src.services.dialogue import extract_and_store_memories
from src.api.gdpr_routes import router as gdpr_router
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from pathlib import Path
import asyncio
import logging
import httpx
from sqlalchemy.exc import OperationalError
from src.services.ollama_online_test import run_ollama_checks

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background threads unless running in explicit test context
    if not getattr(settings, "IS_TEST_ENV", False):
        t = threading.Thread(target=nightly_memory_purge, daemon=True)
        t.start()

        t2 = threading.Thread(target=run_downtime_monitor, daemon=True)
        t2.start()
    else:
        logging.info("Background threads disabled in test environment")

    # Ensure APScheduler is explicitly initialized at application startup
    try:
        SchedulerService.init_scheduler()
    except Exception:
        # Don't let scheduler initialization block app startup; log and continue
        logging.exception("Could not initialize scheduler at startup")

    # Startup info and health checks
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
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
                logging.error(
                    "EMBEDDING_BACKEND=local requires 'sentence-transformers' installed in production."
                )
                logging.error(
                    "Install sentence-transformers or set EMBEDDING_BACKEND=ollama/CLOUD and configure OLLAMA_EMBED_URL."
                )
                raise RuntimeError("Missing 'sentence-transformers' for local embeddings in production")
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

    # --- Trigger embeddings sync failsafe ---
    # Ensure trigger_embeddings table has the correct number of rows matching
    # the canonical STARTER list. If the count is stale (e.g. STARTER grew
    # after a code update), truncate and re-seed from ci_trigger_data.py.
    if not getattr(settings, "IS_TEST_ENV", False):
        try:
            from src.triggers.trigger_matcher import STARTER
            from src.models.database import TriggerEmbedding

            db = SessionLocal()
            try:
                current_count = db.query(TriggerEmbedding).count()
                expected_count = len(STARTER)
                if current_count != expected_count:
                    logging.warning(
                        "Trigger embeddings stale: DB has %d rows but STARTER expects %d. "
                        "Re-seeding from ci_trigger_data.py...",
                        current_count,
                        expected_count,
                    )
                    # Truncate existing rows
                    db.query(TriggerEmbedding).delete()
                    db.commit()

                    # Re-seed from precomputed ci_trigger_data.py
                    import importlib
                    import numpy as np

                    ci_mod = importlib.import_module("scripts.ci_trigger_data")
                    triggers = getattr(ci_mod, "TRIGGERS", None)
                    if isinstance(triggers, list) and len(triggers) == expected_count:
                        for t in triggers:
                            emb = t.get("embedding") or []
                            try:
                                arr = np.array(emb, dtype=np.float32)
                                b = arr.tobytes()
                            except Exception:
                                b = b""
                            te = TriggerEmbedding(
                                name=t.get("name") or "",
                                action_type=t.get("action_type") or "",
                                embedding=b,
                                threshold=float(t.get("threshold", 0.75)),
                            )
                            db.add(te)
                        db.commit()
                        logging.info(
                            "Re-seeded %d trigger embeddings from ci_trigger_data.py",
                            expected_count,
                        )
                    else:
                        logging.error(
                            "ci_trigger_data.py has %d entries but STARTER expects %d; "
                            "skipping re-seed. Run: npm run seed",
                            len(triggers) if triggers else 0,
                            expected_count,
                        )
                else:
                    logging.info(
                        "Trigger embeddings OK: %d rows match STARTER", current_count
                    )
            finally:
                db.close()
        except Exception:
            logging.exception("Trigger embeddings sync failsafe failed")

    yield


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

# Dev Web UI (serve static client and proxy to DialogueEngine) when enabled
DEV_WEB = getattr(settings, "DEV_WEB_CLIENT", False)

# Compute project-relative static path for visibility in logs/debugging
static_path = Path(__file__).resolve().parents[2] / "static" / "dev_web_client"
print(f"DEBUG: settings.DEV_WEB_CLIENT={getattr(settings, 'DEV_WEB_CLIENT', None)}")
print(f"DEBUG: computed static_path={static_path} exists={static_path.exists()}")

if DEV_WEB:
    print("DEBUG: DEV_WEB is True — mounting dev static and router")
    from fastapi.staticfiles import StaticFiles
    from src.api.dev_web_client import router as dev_router

    # Mount static files under /dev/static using project-relative path
    static_dir = str(static_path)
    app.mount("/dev/static", StaticFiles(directory=static_dir), name="dev_static")
    app.include_router(dev_router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


async def process_telegram_batch(user_id: int, external_id: str) -> None:
    """Batch inbound messages for a user and send one AI response.

    When streaming is enabled (``OLLAMA_STREAM_ENABLED``), LLM-generated
    responses are streamed token-by-token to Telegram via progressive
    message edits.  Non-LLM responses (commands, onboarding, lessons, etc.)
    are sent normally as a single message.
    """
    await asyncio.sleep(1.0)

    stream_enabled = getattr(settings, "OLLAMA_STREAM_ENABLED", True)
    logger.info(f"[batch] stream_enabled={stream_enabled} for user_id={user_id}")

    try:
        for _ in range(3):
            message_ids = []
            combined_text = ""

            db = SessionLocal()
            try:
                unprocessed = db.query(MessageLog).filter(
                    MessageLog.user_id == user_id,
                    MessageLog.direction == "inbound",
                    MessageLog.status == "delivered",
                ).order_by(MessageLog.created_at).all()

                if not unprocessed:
                    db.close()
                    break

                if len(unprocessed) > 1:
                    print(f"[batch] Combining {len(unprocessed)} messages from user {user_id}")

                message_ids = [m.message_id for m in unprocessed]
                combined_text = "\n".join([m.content for m in unprocessed if m.content])

                # Claim messages
                db.query(MessageLog).filter(
                    MessageLog.message_id.in_(message_ids)
                ).update({MessageLog.status: "processing"}, synchronize_session=False)
                db.commit()
                db.close()
            except Exception as e:
                print("[batch collection error]", e)
                db.close()
                break

            # Generate AI response — streaming or non-streaming
            chat_id = int(external_id)
            ai_response: str

            if stream_enabled:
                db = SessionLocal()
                dialogue = DialogueEngine(db)
                result = await dialogue.process_message_for_telegram(
                    user_id=user_id,
                    text=combined_text,
                    session=db,
                    chat_id=chat_id,
                    include_history=True,
                    history_turns=4,
                )
                db.close()

                if result["type"] == "stream":
                    # Stream tokens to Telegram via progressive edits
                    logger.info(f"[batch] Using STREAMING path for user_id={user_id}")
                    ai_response, _msg_id = await send_message_streaming(
                        chat_id, result["generator"]
                    )
                    if not ai_response:
                        ai_response = "[No response from LLM]"
                    # Run post-response hooks (trigger matching, etc.)
                    try:
                        await result["post_hook"](ai_response)
                    except Exception as e:
                        print(f"[stream post_hook error] {e}")
                else:
                    # Non-LLM response — send normally
                    logger.info(f"[batch] Using NON-STREAMING (text) path for user_id={user_id}")
                    ai_response = result["text"]
                    await send_message(chat_id, ai_response)
            else:
                # Streaming disabled — use original non-streaming path
                logger.info(f"[batch] OLLAMA_STREAM_ENABLED=False, using NON-STREAMING path for user_id={user_id}")
                db = SessionLocal()
                dialogue = DialogueEngine(db)
                ai_response = await dialogue.process_message(
                    user_id=user_id,
                    text=combined_text,
                    session=db,
                    include_history=True,
                    history_turns=4,
                )
                db.close()
                await send_message(chat_id, ai_response)

            record_traffic_event()

            # Log outbound and mark processed
            try:
                db = SessionLocal()

                # If onboarding is not required, extract and store memories from the combined text.
                if 'dialogue' in locals() and dialogue.onboarding and not dialogue.onboarding.should_show_onboarding(user_id):
                    await extract_and_store_memories(dialogue.memory_manager, dialogue.memory_extractor, user_id, combined_text, rag_mode=False)

                log = MessageLog(
                    user_id=user_id,
                    direction="outbound",
                    channel="telegram",
                    external_message_id=None,
                    content=ai_response,
                    status="sent",
                    error_message=None
                )
                log.message_role = "assistant"
                db.add(log)
                db.commit()

                db.query(MessageLog).filter(
                    MessageLog.message_id.in_(message_ids)
                ).update({MessageLog.status: "processed"}, synchronize_session=False)
                db.commit()
                db.close()
            except Exception as e:
                print("[messagelog outbound error]", e)
                break

            await asyncio.sleep(0.5)
    finally:
        # Release batch lock by deleting from table
        try:
            db = SessionLocal()
            db.query(BatchLock).filter_by(user_id=user_id).delete(synchronize_session=False)
            db.commit()
            db.close()
        except Exception as e:
            print("[batch lock release error]", e)


@app.post("/webhook/telegram/{secret_token}")
async def telegram_webhook(request: Request, secret_token: str):
    # Validate secret token from config
    if secret_token != settings.TELEGRAM_BOT_TOKEN.split(":")[1]:
        raise HTTPException(status_code=403, detail="Forbidden")
    payload = await request.json()
    admin_username = (settings.ADMIN_TELEGRAM_USERNAME or "").lstrip("@").strip().lower()
    if admin_username:
        from_user = payload.get("message", {}).get("from", {})
        if (from_user.get("username") or "").lower() == admin_username:
            chat_id = payload.get("message", {}).get("chat", {}).get("id")
            if chat_id:
                set_admin_chat_id(int(chat_id))
    # Use TelegramHandler to normalize
    parsed = TelegramHandler.parse_webhook(payload)
    if not parsed:
        return {"ok": False, "reason": "Not a valid Telegram message"}
    logging.info(
        "[telegram webhook] user_id=%s message_id=%s channel=telegram",
        parsed.get("user_id"),
        parsed.get("external_message_id"),
    )

    # --- Add or update user in DB ---
    uid = parsed["user_id"]
    text = parsed["text"]
    first_name = payload.get("message", {}).get("from", {}).get("first_name")
    last_name = payload.get("message", {}).get("from", {}).get("last_name")

    db = SessionLocal()
    db_user = db.query(User).filter_by(external_id=str(uid), channel="telegram").first()
    if not db_user:
        db_user = User(
            external_id=str(uid),
            channel="telegram",
            first_name=first_name,
            last_name=last_name,
            opted_in=True
        )
        db.add(db_user)
        db.commit()
        print(f"[user added] {uid} {first_name} {last_name}")
        name = " ".join([n for n in [first_name, last_name] if n]) or str(uid)
        send_admin_notification(f"[INFO] New user joined: {name}.")
    else:
        updated = False
        if first_name and db_user.first_name != first_name:
            db_user.first_name = first_name
            updated = True
        if last_name and db_user.last_name != last_name:
            db_user.last_name = last_name
            updated = True
        if updated:
            db.commit()
            print(f"[user updated] {uid} {first_name} {last_name}")
    # Extract user_id before closing session
    user_id = db_user.user_id if db_user else db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id
    processing_restricted = bool(getattr(db_user, "processing_restricted", False)) if db_user else False
    is_deleted = bool(getattr(db_user, "is_deleted", False)) if db_user else False
    is_opted_in = bool(getattr(db_user, "opted_in", True)) if db_user else True
    db.close()

    if processing_restricted or is_deleted or not is_opted_in:
        return {"ok": True, "restricted": True}

    # Log all incoming messages to MessageLog with retry
    def _log_message():
        db = SessionLocal()
        try:
            user_id = db.query(User).filter_by(external_id=str(uid), channel="telegram").first().user_id if uid else None
            log = MessageLog(
                user_id=user_id,
                direction="inbound",
                channel="telegram",
                external_message_id=parsed["external_message_id"],
                content=text,
                status="delivered",
                error_message=None
            )
            # Only set new columns if they exist (migration applied)
            try:
                log.message_role = "user"
            except:
                pass
            db.add(log)
            db.commit()
        finally:
            db.close()
    
    try:
        _retry_db_op("messagelog", _log_message, attempts=3, delay_seconds=0.1)
    except Exception as e:
        print("[messagelog error]", e)

    record_traffic_event()

    # Schedule background batch processing to allow more messages to arrive
    def _create_batch_lock():
        db = SessionLocal()
        try:
            # Check if lock already exists and is still valid
            existing_lock = db.query(BatchLock).filter(
                BatchLock.user_id == user_id,
                BatchLock.expires_at > datetime.now(timezone.utc)
            ).first()
            
            if not existing_lock:
                # Create new lock (3 minute TTL)
                lock = BatchLock(
                    user_id=user_id,
                    channel="telegram",
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=3)
                )
                db.add(lock)
                db.commit()
                asyncio.create_task(process_telegram_batch(user_id, uid))
        finally:
            db.close()
    
    try:
        _retry_db_op("batch lock", _create_batch_lock, attempts=3, delay_seconds=0.1)
    except Exception as e:
        print("[batch lock error]", e)

    return {"ok": True}


# --- Add a background thread to purge old messages from MessageLog daily ---
def _retry_db_op(op_name: str, func, attempts: int = 3, delay_seconds: float = 1.0):
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except OperationalError as e:
            if attempt == attempts:
                print(f"[{op_name} error] {e}")
                return None
            time.sleep(delay_seconds * attempt)


# `nightly_memory_purge` moved to `src/services/maintenance.py`.

# Startup handled by lifespan
