from __future__ import annotations

"""Ollama LLM client integration.

This module provides a single async entrypoint `call_ollama` which will
prefer the official Ollama client when targeting Ollama Cloud, and use the
local HTTP API for local servers. It normalizes response shapes and includes
clear logging and fallbacks.
"""

import asyncio
import logging
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
OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_TIMEOUT = getattr(settings, "OLLAMA_TIMEOUT", 30.0)
OLLAMA_RETRIES = getattr(settings, "OLLAMA_RETRIES", 2)
OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL")
OLLAMA_LONG_TIMEOUT = getattr(settings, "OLLAMA_LONG_TIMEOUT", 180.0)
OLLAMA_LONG_RETRIES = getattr(settings, "OLLAMA_LONG_RETRIES", 0)


def _is_cloud_url(url: Optional[str]) -> bool:
    if not url:
        return False
    hostname = urlparse(url).hostname or ""
    return "ollama.com" in hostname


def _normalize_local_model_name(model: str) -> str:
    # Cloud models typically have '-cloud' suffix; remove it for local servers
    return model.replace("-cloud", "")


def _extract_chat_text(resp: Any) -> Optional[str]:
    """Try several response shapes and return assistant content if found."""
    try:
        # ChatResponse with attribute `message`
        if hasattr(resp, "message"):
            msg = getattr(resp, "message")
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


async def _call_local_http(model: str, prompt: str) -> str:
    url = getattr(settings, "LOCAL_OLLAMA_URL", OLLAMA_URL)
    payload = {"model": _normalize_local_model_name(model), "prompt": prompt, "stream": False}
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


def _cloud_call_sync(host_base: str, api_key: Optional[str], model: str, prompt: str) -> Any:
    """Sync wrapper executed in a thread: use official `OllamaClient` to call cloud."""
    client = OllamaClient(host=host_base, headers={"Authorization": f"Bearer {api_key}"} if api_key else None)
    messages = [{"role": "user", "content": prompt}]
    # Use non-streaming chat for simplicity
    return client.chat(str(model), messages=messages, stream=False)


async def call_ollama(prompt: str, model: str | None = None, language: str | None = None) -> str:
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

    raw_url = getattr(settings, "OLLAMA_URL", None)
    is_cloud = _is_cloud_url(raw_url)

    # If targeting local but model name is cloud-specific, normalize it
    if not is_cloud and isinstance(chosen_model, str) and "-cloud" in chosen_model:
        logger.debug("Mapping cloud model to local: %s", chosen_model)
        chosen_model = _normalize_local_model_name(chosen_model)

    logger.info("AI PROMPT (model=%s): %s", chosen_model, (prompt[:100] + "...") if len(prompt) > 100 else prompt)

    try:
        if is_cloud and OllamaClient is not None:
            api_key = getattr(settings, "OLLAMA_API_KEY", None)
            parsed = urlparse(raw_url or "https://ollama.com")
            host_base = f"{parsed.scheme}://{parsed.hostname}"

            loop = asyncio.get_running_loop()
            try:
                out = await loop.run_in_executor(None, _cloud_call_sync, host_base, api_key, chosen_model, prompt)
                text = _extract_chat_text(out)
                if text:
                    return text
                # If no text extracted, return stringified response
                return str(out)
            except Exception as e:
                # If cloud reports model missing, try model + '-cloud' once
                err = str(e)
                logger.warning("Cloud client error: %s", err)
                if "not found" in err.lower() and not str(chosen_model).endswith("-cloud"):
                    alt = f"{chosen_model}-cloud"
                    try:
                        out = await loop.run_in_executor(None, _cloud_call_sync, host_base, api_key, alt, prompt)
                        text = _extract_chat_text(out)
                        if text:
                            return text
                        return str(out)
                    except Exception:
                        logger.exception("Retry with -cloud model failed")
                # Fall through to local fallback below

        # Local HTTP path (or fallback if cloud failed)
        return await _call_local_http(chosen_model, prompt)

    except httpx.HTTPStatusError as he:
        logger.exception("Ollama returned HTTP error: %s", he)
        return "[Sorry, I couldn't process your request right now.]"
    except Exception as e:
        logger.exception("[Ollama error] %s", e)
        return "[Sorry, I couldn't process your request right now.]"
