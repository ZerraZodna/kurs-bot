from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from src.memories import MemoryManager
from src.services.maintenance import nightly_memory_purge
from src.middleware.consent import ConsentMiddleware
from src.middleware.api_key_auth import ApiKeyAuthMiddleware
from src.middleware.logging_redaction import apply_logging_redaction
from src.services.security_checks import verify_secrets_config
from src.models.database import SessionLocal, User, MessageLog, BatchLock
from src.config import settings
from src.integrations.telegram import TelegramHandler, send_message
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
import asyncio
import logging
import httpx
from sqlalchemy.exc import OperationalError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background threads
    t = threading.Thread(target=nightly_memory_purge, daemon=True)
    t.start()

    t2 = threading.Thread(target=run_downtime_monitor, daemon=True)
    t2.start()

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
    # Health-check Ollama endpoints. Try local first, then cloud.
    # Health-check Ollama endpoints.
    # Preference: if configured models are cloud (contain '-cloud'), check cloud first.
    # Also: if embeddings use Ollama (`EMBEDDING_BACKEND == 'ollama'`), always verify local availability.
    def _is_cloud_model(m: str | None) -> bool:
        try:
            return isinstance(m, str) and m.endswith("-cloud")
        except Exception:
            return False

    model_main = getattr(settings, "OLLAMA_MODEL", "")
    model_non_english = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", "")
    model_rag = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", "")
    model_is_cloud = any(_is_cloud_model(x) for x in (model_main, model_non_english, model_rag))

    local = getattr(settings, "LOCAL_OLLAMA_URL", None)
    cloud = getattr(settings, "CLOUD_OLLAMA_URL", None)

    # Build candidate order. Rules:
    # - If RAG model explicitly ends with '-cloud', prefer cloud endpoints.
    # - If RAG model is local (no '-cloud') and a local URL is configured, prefer local.
    # - Otherwise, prefer cloud only if a cloud URL is explicitly needed by models.
    candidates = []
    rag_model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None)
    try:
        rag_is_cloud = isinstance(rag_model, str) and rag_model.endswith("-cloud")
    except Exception:
        rag_is_cloud = False
    # Track whether we've successfully checked any preferred endpoints
    checked = False

    if rag_model and not rag_is_cloud and local:
        # RAG model is local; verify local server first to avoid checking cloud.
        candidates.append(local)
        # Optionally allow cloud as a secondary only if models are cloud-marked.
        if model_is_cloud and cloud:
            checked = False
            for base in candidates:
                if not base:
                    continue
                b = _strip_api(base)

                logging.info(f"Checking Ollama endpoint at {b}")
                tags_resp = _probe_tags(b)
                if not tags_resp:
                    continue
                if tags_resp.status_code != 200:
                    logging.warning(f"Ollama AI server responded with status {tags_resp.status_code} at {b}")
                    continue

                logging.info(f"Ollama AI server is running at {b}")

                # Check that RAG model is present (when configured)
                rag_model = getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None)
                if rag_model:
                    embedding_backend = getattr(settings, "EMBEDDING_BACKEND", "local")
                    try:
                        is_cloud_rag = isinstance(rag_model, str) and rag_model.endswith("-cloud")
                    except Exception:
                        is_cloud_rag = False

                    host_is_cloud = _is_cloud_host_url(b)

                    # If the model is local and this host is cloud, skip checking here.
                    if host_is_cloud and not is_cloud_rag:
                        logging.info(
                            "Skipping RAG model '%s' check on cloud host %s because model is local",
                            rag_model,
                            b,
                        )
                        checked = True
                        continue

                    # If the model is cloud-only and this is a local host, skip checking.
                    if not host_is_cloud and is_cloud_rag:
                        logging.info(
                            "Skipping RAG model '%s' check on local host %s because model is cloud-only",
                            rag_model,
                            b,
                        )
                        checked = True
                        continue

                    # Inspect tags for model
                    logging.info("Inspecting /api/tags response for models at %s", b)
                    has_model = _tags_contain_model(tags_resp, rag_model)

                    if not has_model and not host_is_cloud:
                        logging.info("Model '%s' not found in tags at %s; attempting /api/generate ping", rag_model, b)
                        if _attempt_generate_ping(b, rag_model):
                            has_model = True

                    if has_model:
                        logging.info(f"RAG model '{rag_model}' is available at {b}")
                    else:
                        logging.warning(f"RAG model '{rag_model}' not found at {b}; RAG functionality may fail")

                checked = True

            if not checked:
                logging.error("Ollama AI server is NOT reachable at configured endpoints (checked preferred endpoints)")

        checked = True

    if not checked:
        logging.error("Ollama AI server is NOT reachable at configured endpoints (checked preferred endpoints)")

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

    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(ConsentMiddleware)
app.add_middleware(ApiKeyAuthMiddleware)

# Include dialogue routes with context-aware endpoints
app.include_router(dialogue_router)
app.include_router(gdpr_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "kurs-bot prototype"}


async def process_telegram_batch(user_id: int, external_id: str) -> None:
    """Batch inbound messages for a user and send one AI response."""
    await asyncio.sleep(1.0)

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

            # Generate AI response
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

            # Send response back to user
            await send_message(int(external_id), ai_response)
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
