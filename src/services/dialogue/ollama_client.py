from __future__ import annotations

"""Ollama LLM client integration.

This module provides a single async entrypoint `call_ollama` which will
prefer the official Ollama client when targeting Ollama Cloud, and use the
local HTTP API for local servers. It normalizes response shapes and includes
clear logging and fallbacks.
"""

import asyncio
import logging
import time as _time
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from src.config import settings

# Optional official client for cloud usage
try:
    from ollama import Client as OllamaClient
except Exception:
    OllamaClient = None

logger = logging.getLogger(__name__)

# Configurable defaults
# Prefer explicit LOCAL_OLLAMA_URL / CLOUD_OLLAMA_URL
LOCAL_OLLAMA_DEFAULT = "http://localhost:11434/api/generate"
CLOUD_OLLAMA_DEFAULT = "https://ollama.com/api/generate"

LOCAL_OLLAMA_URL = getattr(settings, "LOCAL_OLLAMA_URL", LOCAL_OLLAMA_DEFAULT)
CLOUD_OLLAMA_URL = getattr(settings, "CLOUD_OLLAMA_URL", CLOUD_OLLAMA_DEFAULT)

OLLAMA_TIMEOUT = getattr(settings, "OLLAMA_TIMEOUT", 120.0)
OLLAMA_RETRIES = getattr(settings, "OLLAMA_RETRIES", 1)
OLLAMA_MODEL = settings.OLLAMA_MODEL
OLLAMA_LONG_TIMEOUT = getattr(settings, "OLLAMA_LONG_TIMEOUT", 380.0)
OLLAMA_LONG_RETRIES = getattr(settings, "OLLAMA_LONG_RETRIES", 0)
OLLAMA_TEMPERATURE = getattr(settings, "OLLAMA_TEMPERATURE", 0.2)


def _is_cloud_url(url: Optional[str]) -> bool:
    if not url:
        return False
    hostname = urlparse(url).hostname or ""
    return "ollama.com" in hostname


_TEST_USE_REAL_OLLAMA = bool(getattr(settings, "TEST_USE_REAL_OLLAMA", False))
_IS_TEST_ENV = bool(getattr(settings, "IS_TEST_ENV", False))


# Note: cloud-model name normalization removed. Cloud-only models must run in cloud
# and will not be attempted locally.


def _extract_chat_text(resp: Any) -> Optional[str]:
    """Try several response shapes and return assistant content if found."""
    try:
        # ChatResponse with attribute `message`
        if hasattr(resp, "message"):
            msg = resp.message
            content = getattr(msg, "content", None)
            if content:
                return content
    except Exception:
        pass

    # Iterable of parts: dict, tuples, or Message objects
    try:
        if hasattr(resp, "__iter__") and not isinstance(resp, (str, bytes)):
            parts = list(resp)
            for p in reversed(parts):
                if isinstance(p, dict):
                    m = p.get("message")
                    if isinstance(m, dict):
                        text = m.get("content")
                        if text:
                            return text
                    elif hasattr(m, "content"):
                        text = getattr(m, "content", None)
                        if text:
                            return text

                if isinstance(p, tuple) and len(p) >= 2:
                    key, val = p[0], p[1]
                    if key == "message":
                        m = val
                        if isinstance(m, dict):
                            text = m.get("content")
                            if text:
                                return text
                        elif hasattr(m, "content"):
                            text = getattr(m, "content", None)
                            if text:
                                return text

            # Fallback to stringify last part
            try:
                return str(parts[-1])
            except Exception:
                return None
    except Exception:
        pass

    return None


async def _call_local_http(model: str, prompt: str, temperature: Optional[float] = None) -> str:
    url = LOCAL_OLLAMA_URL
    temp = OLLAMA_TEMPERATURE if temperature is None else temperature
    payload = {"model": model, "prompt": prompt, "stream": False, "temperature": float(temp), "think": False}
    timeout = OLLAMA_LONG_TIMEOUT if "gpt-oss" in model.lower() else OLLAMA_TIMEOUT
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        try:
            data = r.json()
        except Exception:
            return r.text
        if isinstance(data, dict):
            return data.get("response") or data.get("text") or str(data)
        return str(data)


def _cloud_call_sync(host_base: str, api_key: Optional[str], model: str, prompt: str, temperature: float = 0.2) -> Any:
    """Sync wrapper executed in a thread: use official `OllamaClient` to call cloud."""
    client = OllamaClient(host=host_base, headers={"Authorization": f"Bearer {api_key}" } if api_key else None)
    messages = [{"role": "user", "content": prompt}]
    # Use non-streaming chat for simplicity, forward temperature
    try:
        return client.chat(str(model), messages=messages, stream=False, temperature=float(temperature), think=False)
    except TypeError:
        # Older clients may not accept temperature kwarg; fallback
        return client.chat(str(model), messages=messages, stream=False, think=False)


async def stream_ollama(
    prompt: str,
    model: Optional[str] = None,
    language: Optional[str] = None,
    temperature: Optional[float] = None,
):
    """Async generator that yields text chunks from Ollama streaming response.

    Yields partial text tokens as they arrive from the LLM.  The caller is
    responsible for concatenating them into the full response.

    Both local and cloud models stream via the Ollama /api/generate HTTP
    streaming protocol.  Cloud requests include the ``OLLAMA_API_KEY``
    Authorization header and target ``CLOUD_OLLAMA_URL``.

    Falls back to a single-yield of the full response when any error occurs
    mid-stream (network failure, auth error, etc.).
    """
    import json as _json

    chosen_model = model or OLLAMA_MODEL
    if language and language.lower() != "en":
        chosen_model = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", chosen_model)

    # Safety short-circuit for tests
    if _IS_TEST_ENV and not _TEST_USE_REAL_OLLAMA:
        yield "[streaming disabled in test env]"
        return

    # Determine cloud vs local
    raw_url = CLOUD_OLLAMA_URL
    is_cloud = (
        isinstance(chosen_model, str)
        and str(chosen_model).lower().endswith("cloud")
        and _is_cloud_url(raw_url)
    )

    temp = OLLAMA_TEMPERATURE if temperature is None else temperature
    timeout = OLLAMA_LONG_TIMEOUT if "gpt-oss" in chosen_model.lower() else OLLAMA_TIMEOUT

    if is_cloud:
        # Cloud path: stream via httpx against CLOUD_OLLAMA_URL with auth header.
        # Uses the same /api/generate streaming protocol as the local path.
        logger.info("stream_ollama: cloud model detected, using cloud HTTP streaming")
        api_key = getattr(settings, "OLLAMA_API_KEY", None)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        payload = {
            "model": chosen_model,
            "prompt": prompt,
            "stream": True,
            "temperature": float(temp),
            "think": False,
        }
        logger.info(
            "AI STREAM PROMPT cloud (model=%s): %s",
            chosen_model,
            (prompt[:100] + "...") if len(prompt) > 100 else prompt,
        )
        _stream_start = _time.monotonic()
        _token_count = 0
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", raw_url, json=payload, headers=headers, timeout=timeout
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = _json.loads(line)
                        except Exception:
                            continue
                        token = chunk.get("response", "")
                        if token:
                            _token_count += 1
                            # Log first token, every 20th, to keep logs manageable
                            if _token_count == 1 or _token_count % 20 == 0:
                                logger.info(
                                    "[ollama_stream] token #%d at t=+%.3fs len=%d: %r",
                                    _token_count,
                                    _time.monotonic() - _stream_start,
                                    len(token),
                                    token[:30],
                                )
                            yield token
                        if chunk.get("done", False):
                            logger.info(
                                "[ollama_stream] DONE after %d tokens, total elapsed=%.3fs",
                                _token_count,
                                _time.monotonic() - _stream_start,
                            )
                            return
        except Exception as e:
            logger.exception("[stream_ollama cloud error] %s — falling back to non-streaming", e)
            try:
                result = await call_ollama(prompt, model=model, language=language, temperature=temperature)
                yield result
            except Exception:
                yield "[Sorry, I couldn't process your request right now.]"
        return

    # Local HTTP streaming path
    url = LOCAL_OLLAMA_URL
    payload = {
        "model": chosen_model,
        "prompt": prompt,
        "stream": True,
        "temperature": float(temp),
        "think": False,
        "format": "json",  # Force JSON output for consistent function calling
    }

    logger.info(
        "AI STREAM PROMPT (model=%s): %s",
        chosen_model,
        (prompt[:100] + "...") if len(prompt) > 100 else prompt,
    )

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, timeout=timeout) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = _json.loads(line)
                    except Exception:
                        continue
                    token = chunk.get("response", "")
                    if token:
                        yield token
                    # Ollama signals end of stream with "done": true
                    if chunk.get("done", False):
                        return
    except Exception as e:
        logger.exception("[stream_ollama error] %s — falling back to non-streaming", e)
        # Fallback: yield full response from non-streaming call
        try:
            result = await call_ollama(prompt, model=model, language=language, temperature=temperature)
            yield result
        except Exception:
            yield "[Sorry, I couldn't process your request right now.]"


async def call_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None, temperature: Optional[float] = None) -> str:
    """Top-level async method to call Ollama (cloud or local) and return text.

    Behavior summary:
    - If settings.OLLAMA_URL points at ollama.com and `ollama` client is available,
      use the official client (in a thread) and extract text from its response.
    - Otherwise use the local HTTP API via `httpx`.
    - For cloud model-not-found errors, attempt a '-cloud' suffix retry.
    """
    chosen_model = model or OLLAMA_MODEL
    if language and language.lower() != "en":
        chosen_model = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", chosen_model)

    # Safety short-circuit: only block real calls in explicit test context.
    # In production (IS_TEST_ENV=False), always allow real Ollama regardless
    # of TEST_USE_REAL_OLLAMA.
    if _IS_TEST_ENV and not _TEST_USE_REAL_OLLAMA:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        raise RuntimeError(
            "Real Ollama calls are disabled in this test process (TEST_USE_REAL_OLLAMA is falsy). "
            f"Attempted model={chosen_model or 'none'} lang={language or 'en'} prompt_snippet={short[:200]}"
        )

    # Determine cloud vs local endpoint. Use cloud ONLY when the model
    # explicitly ends with '-cloud' and a cloud URL is configured.
    raw_url = CLOUD_OLLAMA_URL
    is_cloud_url_configured = _is_cloud_url(raw_url)
    is_cloud = isinstance(chosen_model, str) and str(chosen_model).lower().endswith("cloud") and is_cloud_url_configured

    # If the model explicitly indicates a cloud variant but CLOUD_OLLAMA_URL is
    # not configured, DO NOT attempt to call local Ollama — treat as unavailable.
    if isinstance(chosen_model, str) and str(chosen_model).lower().endswith("cloud") and not is_cloud_url_configured:
        logger.error("Cloud model requested but CLOUD_OLLAMA_URL not configured: %s", chosen_model)
        if _TEST_USE_REAL_OLLAMA:
            raise RuntimeError("Cloud Ollama requested but CLOUD_OLLAMA_URL not configured")
        return "[Ollama cloud model requested but cloud endpoint is not configured.]"

    logger.info("AI PROMPT (model=%s): %s", chosen_model, (prompt[:100] + "...") if len(prompt) > 100 else prompt)

    try:
        if is_cloud:
            if OllamaClient is None:
                logger.error("Ollama cloud client library not installed; cannot call cloud models")
                if _TEST_USE_REAL_OLLAMA:
                    raise RuntimeError("Ollama client library not available for cloud calls")
                return "[Ollama cloud client not available on this host]"
            # proceed with cloud call
            api_key = getattr(settings, "OLLAMA_API_KEY", None)
            parsed = urlparse(raw_url or CLOUD_OLLAMA_DEFAULT)
            host_base = f"{parsed.scheme}://{parsed.hostname}"

            loop = asyncio.get_running_loop()
            try:
                temp = OLLAMA_TEMPERATURE if temperature is None else temperature
                out = await loop.run_in_executor(None, _cloud_call_sync, host_base, api_key, chosen_model, prompt, float(temp))
                text = _extract_chat_text(out)
                if text:
                    return text
                return str(out)
            except Exception as e:
                err = str(e)
                logger.warning("Cloud client error: %s", err)
                if _TEST_USE_REAL_OLLAMA:
                    raise
                return "[Sorry, I couldn't process your request right now.]"

        # Local HTTP path (or fallback if cloud failed)
        temp = OLLAMA_TEMPERATURE if temperature is None else temperature
        return await _call_local_http(chosen_model, prompt, temperature=float(temp))

    except httpx.HTTPStatusError as he:
        logger.exception("Ollama returned HTTP error: %s", he)
        if _TEST_USE_REAL_OLLAMA:
            raise
        return "[Sorry, I couldn't process your request right now.]"
    except Exception as e:
        logger.exception("[Ollama error] %s", e)
        if _TEST_USE_REAL_OLLAMA:
            raise
        return "[Sorry, I couldn't process your request right now.]"
