"""Helpers to test Ollama availability and configured models.

Small, synchronous helpers used by the FastAPI startup lifespan to keep
the health-check logic organized and testable.
"""
from typing import Dict, List, Tuple
from urllib.parse import urlparse
import logging
import re
import httpx


def _is_cloud_model(model: str | None) -> bool:
    try:
        return isinstance(model, str) and str(model).lower().endswith("cloud")
    except Exception:
        return False


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


def _probe_tags(base: str, timeout: float = 2.0):
    try:
        return httpx.get(f"{base}/api/tags", timeout=timeout)
    except Exception as e:
        logging.debug("_probe_tags error for %s: %s", base, e)
        return None


def _attempt_generate_ping(base: str, model: str | None, timeout: float = 3.0) -> bool:
    try:
        ping = httpx.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": "ping", "stream": False},
            timeout=timeout,
        )
        return ping.status_code == 200
    except Exception:
        logging.debug("/api/generate ping failed at %s for model %s", base, model)
        return False


def run_ollama_checks(settings) -> Tuple[bool, List[Dict]]:
    """Perform the three-step checks described by the user.

    1) Build model table from settings and detect which models are cloud-marked.
    2) If any cloud models exist, check the cloud endpoint and confirm listed tags.
    3) If any non-cloud models exist, check the local endpoint and confirm models
       via /api/tags or fallback /api/generate pings.

    Returns (any_ok, diagnostics)
    """
    diagnostics: List[Dict] = []

    local = getattr(settings, "LOCAL_OLLAMA_URL", None)
    cloud = getattr(settings, "CLOUD_OLLAMA_URL", None)

    # Collect models
    models = {
        "OLLAMA_MODEL": getattr(settings, "OLLAMA_MODEL", None),
        "NON_ENGLISH_OLLAMA_MODEL": getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", None),
        "OLLAMA_CHAT_RAG_MODEL": getattr(settings, "OLLAMA_CHAT_RAG_MODEL", None),
    }

    # Build explicit model table
    cloud_models = {k: v for k, v in models.items() if _is_cloud_model(v)}
    local_models = {k: v for k, v in models.items() if v and not _is_cloud_model(v)}

    any_ok = True

    # Step A: If any cloud-marked models exist, check cloud service and /api/tags
    if cloud_models:
        if not cloud:
            diagnostics.append({"error": "cloud models configured but CLOUD_OLLAMA_URL not set", "models": cloud_models})
            any_ok = False
        else:
            b = _strip_api(cloud)
            logging.info("Checking cloud Ollama endpoint at %s", b)
            tags = _probe_tags(b)
            entry = {"base": b, "kind": "cloud", "tags_status": None, "models": {}}
            if tags is None:
                entry["tags_error"] = "no_response"
                any_ok = False
            else:
                entry["tags_status"] = int(getattr(tags, "status_code", 0) or 0)
                names = set()
                if tags.status_code == 200:
                    try:
                        data = tags.json()
                        # The /api/tags response may be a list or a dict containing
                        # a 'models' or 'data' list. Handle common shapes robustly.
                        model_items = []
                        if isinstance(data, list):
                            model_items = data
                        elif isinstance(data, dict):
                            # Prefer 'models' or 'data' keys when present
                            if isinstance(data.get("models"), list):
                                model_items = data.get("models")
                            elif isinstance(data.get("data"), list):
                                model_items = data.get("data")
                            else:
                                # Fallback: consider the dict's values as possible items
                                model_items = list(data.values())

                        for item in model_items:
                            if isinstance(item, dict):
                                # Common keys: 'name' or 'model'
                                n = item.get("name") or item.get("model")
                            else:
                                n = item
                            if n:
                                names.add(str(n).lower())

                        # Raw tags payload available in logs at debug level
                    except Exception:
                        logging.exception("Failed parsing /api/tags on cloud %s", b)
                # DEBUG: expose the names we found from /api/tags (kept at debug level)
                logging.debug("cloud /api/tags names: %s", names)
                # Check each cloud model presence in tags. Cloud-marked model names
                # may include the '-cloud' suffix while the /api/tags list the
                # canonical model name without that suffix. Match both variants.
                for k, m in cloud_models.items():
                    model_name = str(m)
                    try:
                        stripped = re.sub(r"[:\-]?\d*-?cloud$", "", model_name, flags=re.IGNORECASE).lower()
                    except Exception:
                        stripped = model_name.lower()
                    found = (model_name in names) or (stripped in names)
                    # DEBUG: log the comparison for easier troubleshooting
                    logging.debug(
                        "cloud model check %s -> found=%s (model_name=%s, stripped=%s)",
                        k,
                        found,
                        model_name,
                        stripped,
                    )
                    entry["models"][k] = {"model": m, "found": found}
                    if not found:
                        any_ok = False
            diagnostics.append(entry)

    # Step B: If any non-cloud models exist, check local service and verify with /api/generate
    # Note: /api/tags is used only for cloud models per requirement; local models are
    # verified by attempting /api/generate for each model name.
    if local_models:
        if not local:
            diagnostics.append({"error": "local models configured but LOCAL_OLLAMA_URL not set", "models": local_models})
            any_ok = False
        else:
            b = _strip_api(local)
            logging.info("Checking local Ollama endpoint at %s (verifying models via /api/generate)", b)
            entry = {"base": b, "kind": "local", "models": {}}

            for k, m in local_models.items():
                # For local models, call /api/generate to confirm the model responds
                try:
                    ping_ok = _attempt_generate_ping(b, m)
                except Exception:
                    ping_ok = False
                entry["models"][k] = {"model": m, "found": bool(ping_ok)}
                if not ping_ok:
                    any_ok = False

            diagnostics.append(entry)

    # If no models at all, note this but treat as ok
    if not cloud_models and not local_models:
        diagnostics.append({"note": "no ollama models configured in settings"})

    return any_ok, diagnostics
