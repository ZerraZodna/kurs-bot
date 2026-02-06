"""Ollama LLM client integration."""

from __future__ import annotations

import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"


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

    # Log the prompt (truncated) for debugging
    try:
        preview = prompt if prompt is None or len(prompt) <= 2000 else prompt[:2000] + "..."
        logger.info("AI PROMPT (model=%s): %s", model, preview)
    except Exception:
        logger.info("AI PROMPT (model=%s): [unable to render prompt]", model)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)

            # Log status and response body (truncated)
            try:
                logger.info("Ollama HTTP %s", response.status_code)
            except Exception:
                pass
            try:
                text = response.text
                preview = text if len(text) <= 2000 else text[:2000] + "..."
                logger.debug("Ollama response body: %s", preview)
            except Exception:
                logger.debug("Ollama response body: [unreadable]")

            response.raise_for_status()
            data = response.json()

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
        logger.error(f"[Ollama error] {e}")
        return "[Sorry, I couldn't process your request right now.]"
