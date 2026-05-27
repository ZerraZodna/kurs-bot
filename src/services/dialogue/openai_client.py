from __future__ import annotations

"""OpenAI-compatible LLM client integration.

This module provides a single async entrypoint ``call_llm`` which delegates to
any OpenAI-compatible server (OpenAI, local servers like Pi's, Groq, Together,
etc.).  It mirrors the interface of ``ollama_client.py`` so that the rest of
the codebase can call either provider through a unified routing layer in
``dialogue_engine.py``.

Both non-streaming and streaming paths are supported.  Streaming uses the
OpenAI SSE protocol (``data: {"choices": [{"delta": {"content": ...}}]}``).
"""

import logging
import time as _time
from typing import Any

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable defaults (mirrors ollama_client.py pattern)
# ---------------------------------------------------------------------------
OPENAI_TIMEOUT = getattr(settings, "OPENAI_TIMEOUT", 120.0)
OPENAI_LONG_TIMEOUT = getattr(settings, "OPENAI_LONG_TIMEOUT", 380.0)
OPENAI_MODEL = settings.OPENAI_MODEL
OPENAI_TEMPERATURE = getattr(settings, "OPENAI_TEMPERATURE", 0.2)

_IS_TEST_ENV = bool(getattr(settings, "IS_TEST_ENV", False))
_TEST_USE_REAL_OLLAMA = bool(getattr(settings, "TEST_USE_REAL_OLLAMA", False))


def _is_long_model(model: str) -> bool:
    """Return True for models that need extended timeouts."""
    return "gpt-oss" in (model or "").lower()


def _build_client_kwargs() -> dict[str, Any]:
    """Build kwargs for AsyncOpenAI constructor."""
    kwargs: dict[str, Any] = {}
    base_url = getattr(settings, "OPENAI_BASE_URL", None)
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


# ---------------------------------------------------------------------------
# Non-streaming entry point
# ---------------------------------------------------------------------------

async def call_llm(
    prompt: str,
    model: str | None = None,
    language: str | None = None,
    temperature: float | None = None,
) -> str:
    """Make a non-streaming request to an OpenAI-compatible server.

    Parameters
    ----------
    prompt : str
        The full prompt (system instructions are already embedded).
    model : str, optional
        Model name.  Falls back to ``settings.OPENAI_MODEL``.
    language : str, optional
        Language hint (kept for API parity with ``ollama_client.call_ollama``).
    temperature : float, optional
        Sampling temperature.  Falls back to ``settings.OPENAI_TEMPERATURE``.

    Returns
    -------
    str
        The assistant's response text, or a friendly error message on failure.
    """
    chosen_model = model or OPENAI_MODEL
    if language and language.lower() != "en":
        chosen_model = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", chosen_model)

    # Safety short-circuit for tests
    if _IS_TEST_ENV and not _TEST_USE_REAL_OLLAMA:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        raise RuntimeError(
            "Real OpenAI calls are disabled in this test process (TEST_USE_REAL_OLLAMA is falsy). "
            f"Attempted model={chosen_model or 'none'} lang={language or 'en'} prompt_snippet={short[:200]}"
        )

    temp = OPENAI_TEMPERATURE if temperature is None else temperature
    timeout = OPENAI_LONG_TIMEOUT if _is_long_model(chosen_model) else OPENAI_TIMEOUT

    logger.info("AI PROMPT openai (model=%s): %s", chosen_model, (prompt[:100] + "...") if len(prompt) > 100 else prompt)

    try:
        client = AsyncOpenAI(**_build_client_kwargs())
        response = await client.chat.completions.create(
            model=chosen_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=float(temp),
            timeout=timeout,
        )

        if response.choices:
            content = response.choices[0].message.content
            if content:
                return content

        logger.warning("OpenAI response had no choices or empty content")
        return "[No response from LLM]"

    except Exception as e:
        logger.exception("[OpenAI error] %s", e)
        if _TEST_USE_REAL_OLLAMA:
            raise
        return "[Sorry, I couldn't process your request right now.]"


# ---------------------------------------------------------------------------
# Streaming entry point
# ---------------------------------------------------------------------------

async def stream_llm(
    prompt: str,
    model: str | None = None,
    language: str | None = None,
    temperature: float | None = None,
):
    """Async generator that yields text chunks from an OpenAI-compatible server.

    Yields partial text tokens as they arrive via SSE.  The caller is
    responsible for concatenating them into the full response.

    Falls back to a single-yield of the full response when any error occurs
    mid-stream (network failure, auth error, etc.).
    """
    chosen_model = model or OPENAI_MODEL
    if language and language.lower() != "en":
        chosen_model = getattr(settings, "NON_ENGLISH_OLLAMA_MODEL", chosen_model)

    # Safety short-circuit for tests
    if _IS_TEST_ENV and not _TEST_USE_REAL_OLLAMA:
        yield "[streaming disabled in test env]"
        return

    temp = OPENAI_TEMPERATURE if temperature is None else temperature
    timeout = OPENAI_LONG_TIMEOUT if _is_long_model(chosen_model) else OPENAI_TIMEOUT

    logger.info(
        "AI STREAM PROMPT openai (model=%s): %s",
        chosen_model,
        (prompt[:100] + "...") if len(prompt) > 100 else prompt,
    )

    try:
        client = AsyncOpenAI(**_build_client_kwargs())
        response = await client.chat.completions.create(
            model=chosen_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=float(temp),
            stream=True,
            timeout=timeout,
        )

        _stream_start = _time.monotonic()
        _token_count = 0

        async for chunk in response:
            content = chunk.choices[0].delta.content if chunk.choices else None
            if content:
                _token_count += 1
                if _token_count == 1 or _token_count % 20 == 0:
                    logger.info(
                        "[openai_stream] token #%d at t=+%.3fs len=%d: %r",
                        _token_count,
                        _time.monotonic() - _stream_start,
                        len(content),
                        content[:30],
                    )
                yield content

            # OpenAI signals end with finish_reason
            if chunk.choices and chunk.choices[0].finish_reason is not None:
                logger.info(
                    "[openai_stream] DONE after %d tokens, total elapsed=%.3fs",
                    _token_count,
                    _time.monotonic() - _stream_start,
                )
                return

    except Exception as e:
        logger.exception("[stream_llm error] %s — falling back to non-streaming", e)
        try:
            result = await call_llm(prompt, model=model, language=language, temperature=temperature)
            yield result
        except Exception:
            yield "[Sorry, I couldn't process your request right now.]"
