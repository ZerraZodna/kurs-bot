"""Ollama LLM client integration."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import httpx
from src.config import settings

# Try to import official Ollama client if available; optional dependency
try:
    from ollama import Client as OllamaClient
except Exception:
    OllamaClient = None

logger = logging.getLogger(__name__)

# Configurable endpoint, timeout and retries
OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_TIMEOUT = getattr(settings, "OLLAMA_TIMEOUT", 30.0)
OLLAMA_RETRIES = getattr(settings, "OLLAMA_RETRIES", 2)
OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL")
# Optional longer single timeout for very large models (no retries)
OLLAMA_LONG_TIMEOUT = getattr(settings, "OLLAMA_LONG_TIMEOUT", 180.0)
OLLAMA_LONG_RETRIES = getattr(settings, "OLLAMA_LONG_RETRIES", 0)
# Cache config flag at import time for fast checks
#SHOW_AI_PROMPT = getattr(settings, "SHOW_AI_PROMPT", False)

async def call_ollama(prompt: str, model: str | None = None, language: str | None = None) -> str:
    """
    Call Ollama LLM with a prompt.

    Args:
        prompt: The prompt to send to Ollama
        model: Model name (defaults to settings.OLLAMA_MODEL)

    Returns:
        Response text from Ollama
    """
    # Determine whether we're targeting Ollama Cloud or a local Ollama server
    raw_settings_url = getattr(settings, "OLLAMA_URL", None)
    parsed = urlparse(raw_settings_url or "http://localhost:11434")
    is_ollama_cloud = parsed.hostname and "ollama.com" in parsed.hostname

    # If an explicit model is provided, use it. Otherwise, choose based on ISO language code.
    # Treat `en` as English; any other ISO code selects the NON_ENGLISH model.
    if model:
        chosen_model = model
    else:
        chosen_model = OLLAMA_MODEL
        if language and language.lower() != "en":
            chosen_model = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", settings.OLLAMA_MODEL)

    # If we're calling a local Ollama server (not cloud) but the configured
    # model name is the cloud variant (commonly ending with '-cloud'), map it
    # to the equivalent local model name by removing the '-cloud' suffix.
    if not is_ollama_cloud and isinstance(chosen_model, str) and "-cloud" in chosen_model:
        logger.info("Mapping cloud model name to local model: %s -> %s", chosen_model, chosen_model.replace('-cloud', ''))
        chosen_model = chosen_model.replace('-cloud', '')

    payload = {"model": chosen_model, "prompt": prompt, "stream": False}

    # Log the prompt (truncated) for debugging when enabled via config
    #if SHOW_AI_PROMPT:
    preview = prompt if prompt is None or len(prompt) <= 100 else prompt[:100] + "..."
    logger.info("AI PROMPT (model=%s): %s", chosen_model, preview)

    try:
        # For very large models (e.g. gpt-oss) prefer a single long timeout
        # instead of multiple short retries. Detect by model name.
        model_lower = str(chosen_model).lower() if chosen_model else ""
        if "gpt-oss" in model_lower or "gpt_oss" in model_lower:
            timeout = OLLAMA_LONG_TIMEOUT
            retries = OLLAMA_LONG_RETRIES
        else:
            timeout = OLLAMA_TIMEOUT
            retries = OLLAMA_RETRIES

        # If using Ollama Cloud (ollama.com) prefer the official client which
        # handles cloud endpoints and auth correctly. Fall back to httpx.
        api_key = getattr(settings, "OLLAMA_API_KEY", None)
        logger.info("OLLAMA settings URL: %s", raw_settings_url)
        logger.info("Parsed OLLAMA host=%s is_ollama_cloud=%s", parsed.hostname, bool(is_ollama_cloud))

        if is_ollama_cloud and OllamaClient is not None:
            # Use official (sync) Ollama client in a thread to avoid blocking.
            # Use the configured settings value for the API key (not os.environ),
            # because pydantic may load the key from .env into `settings` without
            # exporting it into the process environment.
            def call_sync():
                host_base = f"{parsed.scheme}://{parsed.hostname}"
                headers_arg = {"Authorization": f"Bearer {api_key}"} if api_key else None

                client = OllamaClient(host=host_base, headers=headers_arg)

                # Prepare messages in the expected format
                messages = [{"role": "user", "content": prompt}]

                # Prefer chat API which supports streaming; request a single non-streamed response
                try:
                    out = client.chat(str(chosen_model), messages=messages, stream=False)

                    # Helper: extract assistant content from various response shapes
                    def _extract_chat_text(resp):
                        # If response has attribute 'message' with content
                        try:
                            if hasattr(resp, 'message'):
                                msg = getattr(resp, 'message')
                                if hasattr(msg, 'content') and getattr(msg, 'content'):
                                    return getattr(msg, 'content')
                        except Exception:
                            pass

                        # If iterable (list of parts), handle tuple/dict/Message types
                        try:
                            if hasattr(resp, '__iter__') and not isinstance(resp, (str, bytes)):
                                parts = list(resp)
                                for p in reversed(parts):
                                    # dict-like part
                                    if isinstance(p, dict):
                                        m = p.get('message')
                                        if isinstance(m, dict):
                                            text = m.get('content')
                                            if text:
                                                return text
                                        elif hasattr(m, 'content'):
                                            text = getattr(m, 'content', None)
                                            if text:
                                                return text
                                    # tuple-like part e.g. ('message', Message(...))
                                    if isinstance(p, tuple) and len(p) >= 2:
                                        key, val = p[0], p[1]
                                        if key == 'message':
                                            m = val
                                            if isinstance(m, dict):
                                                text = m.get('content')
                                                if text:
                                                    return text
                                            elif hasattr(m, 'content'):
                                                text = getattr(m, 'content', None)
                                                if text:
                                                    return text
                                # Fallback: try to stringify last element
                                try:
                                    return str(parts[-1])
                                except Exception:
                                    return None
                        except Exception:
                            pass

                        return None

                    text = _extract_chat_text(out)
                    if text:
                        return text

                    # If extraction failed, fall back to returning full response
                    return out
                except Exception as e:
                    # If model not found on cloud, try appending '-cloud' and retry once
                    se = str(e)
                    if is_ollama_cloud and not str(chosen_model).endswith("-cloud") and "not found" in se.lower():
                        alt_model = f"{chosen_model}-cloud"
                        try:
                            out = client.chat(str(alt_model), messages=messages, stream=False)
                            text = _extract_chat_text(out)
                            if text:
                                return text
                            return out
                        except Exception:
                            # fall through to original fallback
                            pass

                        # Fall back to generate API if available; if that fails, try local HTTP endpoint
                        try:
                            out = client.generate(model=str(chosen_model), prompt=prompt)
                            return out
                        except Exception as gen_exc:
                            logger.warning("Cloud client generate failed: %s; attempting local HTTP fallback", gen_exc)
                            # Attempt to call a local Ollama HTTP endpoint as a last resort
                            local_url = getattr(settings, "LOCAL_OLLAMA_URL", "http://localhost:11434/api/generate")
                            # Use a non-cloud model name for local if needed
                            local_model = str(chosen_model).replace("-cloud", "")
                            local_payload = {"model": local_model, "prompt": prompt, "stream": False}
                            try:
                                import httpx as _httpx
                                with _httpx.Client() as sync_client:
                                    r = sync_client.post(local_url, json=local_payload, timeout=30.0)
                                    r.raise_for_status()
                                    try:
                                        data = r.json()
                                    except Exception:
                                        return r.text
                                    # Prefer 'response' key, then try common keys
                                    if isinstance(data, dict):
                                        return data.get("response") or data.get("text") or str(data)
                                    return str(data)
                            except Exception:
                                # re-raise original cloud generate exception for visibility
                                raise gen_exc

            loop = asyncio.get_running_loop()
            try:
                resp_text = await loop.run_in_executor(None, call_sync)
                return resp_text or "[No response from Ollama]"
            except Exception as e:
                logger.exception("[Ollama client error] %s", e)
                return "[Sorry, I couldn't process your request right now.]"

        # Build request headers; include Authorization if an API key is configured
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient() as client:
            # Retry on read timeouts with simple exponential backoff
            backoff = 0.5
            response = None
            for attempt in range(0, retries + 1):
                try:
                    response = await client.post(OLLAMA_URL, json=payload, headers=headers or None, timeout=timeout)
                    break
                except httpx.ReadTimeout:
                    if attempt < retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        logger.warning("Ollama read timeout, retrying (attempt=%s)", attempt + 1)
                        continue
                    else:
                        logger.exception("Ollama read timeout after %s attempts", retries + 1)
                        return "[Sorry, I couldn't process your request right now.]"

            # Log status and response body (truncated)
            logger.info("Ollama HTTP %s", response.status_code)
            # Build a safe, truncated preview of the response body for logs
            if response is None:
                previewResponse = None
            else:
                try:
                    body_text = response.text or ""
                except Exception:
                    body_text = "[unreadable]"
                previewResponse = body_text if len(body_text) <= 50 else body_text[:50] + "..."
            logger.info("AI RESPONSE: %s", previewResponse)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                # Log full response body on non-2xx status for easier debugging
                try:
                    body = response.text
                except Exception:
                    body = "[unreadable]"
                logger.error(
                    "Ollama returned non-2xx status %s. Body: %s",
                    response.status_code,
                    body,
                )
                return "[Sorry, I couldn't process your request right now.]"

            # Parse JSON body
            try:
                data = response.json()
            except Exception as ex:
                logger.error("Failed to parse JSON from Ollama response: %s", ex)
                return "[Sorry, I couldn't process your request right now.]"

            if data is None:
                logger.warning("Ollama returned empty JSON body")
                return "[No response from Ollama]"

            try:
                resp_text = data.get("response")
            except Exception:
                # If data isn't a mapping, coerce to string
                try:
                    return str(data)
                except Exception:
                    return "[No response from Ollama]"

            return resp_text or "[No response from Ollama]"

    except Exception as e:
        # Include full traceback in logs for diagnosis
        logger.exception("[Ollama error] %s", e)
        return "[Sorry, I couldn't process your request right now.]"
