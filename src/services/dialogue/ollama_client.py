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
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "[No response from Ollama]")
    except Exception as e:
        logger.error(f"[Ollama error] {e}")
        return "[Sorry, I couldn't process your request right now.]"
