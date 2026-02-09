"""Ollama LLM client integration."""

from __future__ import annotations

import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

# Read Ollama endpoint from settings so it's configurable like elsewhere
OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434/api/generate")
# Cache config flag at import time for fast checks
#SHOW_AI_PROMPT = getattr(settings, "SHOW_AI_PROMPT", False)


async def call_ollama(prompt: str, model: str | None = None) -> str:
    """
    Call Ollama LLM with a prompt.

    Args:
        prompt: The prompt to send to Ollama
        model: Model name (defaults to settings.OLLAMA_MODEL)

    Returns:
        Response text from Ollama
    """
    model = model or settings.OLLAMA_MODEL
    payload = {"model": model, "prompt": prompt, "stream": False}

    # Log the prompt (truncated) for debugging when enabled via config
    #if SHOW_AI_PROMPT:
    preview = prompt if prompt is None or len(prompt) <= 100 else prompt[:100] + "..."
    logger.info("AI PROMPT (model=%s): %s", model, preview)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)

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
