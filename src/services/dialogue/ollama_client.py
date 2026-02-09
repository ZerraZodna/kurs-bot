"""Ollama LLM client integration."""

from __future__ import annotations

import asyncio
import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

# Configurable endpoint, timeout and retries
OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_TIMEOUT = getattr(settings, "OLLAMA_TIMEOUT", 30.0)
OLLAMA_RETRIES = getattr(settings, "OLLAMA_RETRIES", 2)
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
    # If an explicit model is provided, use it. Otherwise, choose based on language.
    if language and language.lower() != "english":
        chosen_model = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", settings.OLLAMA_MODEL)
    else:
        if model:
            chosen_model = model
        else:
            chosen_model = settings.OLLAMA_MODEL
    model = chosen_model
    payload = {"model": model, "prompt": prompt, "stream": False}

    # Log the prompt (truncated) for debugging when enabled via config
    #if SHOW_AI_PROMPT:
    preview = prompt if prompt is None or len(prompt) <= 100 else prompt[:100] + "..."
    logger.info("AI PROMPT (model=%s): %s", model, preview)

    try:
        # For very large models (e.g. gpt-oss) prefer a single long timeout
        # instead of multiple short retries. Detect by model name.
        model_lower = str(model).lower() if model else ""
        if "gpt-oss" in model_lower or "gpt_oss" in model_lower:
            timeout = OLLAMA_LONG_TIMEOUT
            retries = OLLAMA_LONG_RETRIES
        else:
            timeout = OLLAMA_TIMEOUT
            retries = OLLAMA_RETRIES

        async with httpx.AsyncClient() as client:
            # Retry on read timeouts with simple exponential backoff
            backoff = 0.5
            response = None
            for attempt in range(0, retries + 1):
                try:
                    response = await client.post(OLLAMA_URL, json=payload, timeout=timeout)
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
            #if SHOW_AI_PROMPT:
            #    logger.info("Raw LLM response (repr): %r", response)

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
