# TODO: Add OpenAI-Compatible LLM Provider (Additive, No Refactor)

> **Goal:** Add support for any OpenAI-compatible LLM server (OpenAI, local servers like Pi's, Groq, Together, etc.) alongside the existing Ollama setup. Zero changes to existing Ollama code — pure additive.

---

## Overview

The app currently uses `src/services/dialogue/ollama_client.py` as its sole LLM integration. All callers (`dialogue_engine.py`, `translation_service.py`, etc.) call `call_ollama()` and `stream_ollama()` generically.

**Strategy: Additive only.** Create a new `openai_client.py` module with parallel `call_llm()` and `stream_llm()` functions. Add a `LLM_PROVIDER` config switch. Wire it in `dialogue_engine.py` with an `if/else` — no refactoring of the Ollama code.

The `openai` SDK (`==2.38.0`) is already installed.

---

## Steps

### Step 1: Add OpenAI config settings to `src/config.py`

**File:** `src/config.py`

Add new settings alongside existing Ollama settings:

```python
# OpenAI / OpenAI-compatible settings
OPENAI_API_KEY: str = ""
OPENAI_BASE_URL: str = ""  # Empty = default OpenAI; set for compatible servers
OPENAI_MODEL: str = "gpt-4o"
OPENAI_TIMEOUT: float = 120.0
OPENAI_LONG_TIMEOUT: float = 380.0
OPENAI_TEMPERATURE: float = 0.2
LLM_PROVIDER: str = "ollama"  # "ollama" | "openai"
```

- `OPENAI_BASE_URL` empty → uses default OpenAI API
- `OPENAI_BASE_URL` set → uses that as the `/v1/chat/completions` base (for local servers, Groq, Together, etc.)
- `LLM_PROVIDER` defaults to `"ollama"` for zero impact on existing deployments
- `OPENAI_TEMPERATURE` defaults to same as `OLLAMA_TEMPERATURE` (0.2)

---

### Step 2: Create `src/services/dialogue/openai_client.py`

**File:** `src/services/dialogue/openai_client.py` (**NEW**)

Mirror the structure of `ollama_client.py` but for OpenAI-compatible servers.

#### 2a. Non-streaming `call_llm()`

```python
async def call_llm(
    prompt: str,
    model: str | None = None,
    language: str | None = None,
    temperature: float | None = None,
) -> str:
```

**Key differences from Ollama:**

| Aspect | Ollama | OpenAI-compatible |
|--------|--------|-------------------|
| Request body | `{"model": ..., "prompt": ..., "stream": false}` | `{"model": ..., "messages": [{"role": "user", "content": ...}]}` |
| Response | `data["response"]` or `data["text"]` | `response.choices[0].message.content` |
| Auth | Optional Bearer | `Authorization: Bearer <key>` |
| Endpoint | `/api/generate` | `{base_url}/v1/chat/completions` |

**Implementation details:**
- Use `openai.AsyncOpenAI` (async SDK) — cleaner than httpx
- Build messages array: `[{"role": "user", "content": prompt}]` (the prompt already contains system instructions)
- Extract text from `response.choices[0].message.content`
- Log request/response same as Ollama client
- Handle test env short-circuit (`IS_TEST_ENV` + `not TEST_USE_REAL_OLLAMA`)
- Return `"[Sorry, I couldn't process your request right now.]"` on errors (same as Ollama)

#### 2b. Streaming `stream_llm()`

```python
async def stream_llm(
    prompt: str,
    model: str | None = None,
    language: str | None = None,
    temperature: float | None = None,
):
```

**Key differences from Ollama streaming:**

| Aspect | Ollama | OpenAI-compatible |
|--------|--------|-------------------|
| Protocol | Line-delimited JSON (`{"response": "t", "done": true}`) | SSE (`data: {"choices": [{"delta": {"content": "t"}}]}`) |
| End signal | `"done": true` chunk | `finish_reason: "stop"` in final chunk |

**Implementation details:**
- Use `openai.AsyncOpenAI.chat.completions.create(stream=True)`
- Iterate chunks: `for chunk in response: content = chunk.choices[0].delta.content or ""`
- Yield each non-empty `content` token (same as Ollama's `chunk.get("response", "")`)
- Log first token, every 20th token (same pattern as Ollama)
- Fall back to non-streaming `call_llm()` on any error (same as Ollama)
- Test env short-circuit: yield `"[streaming disabled in test env]"`

#### 2c. Config constants at module level

Mirror Ollama client's pattern:

```python
OPENAI_TIMEOUT = getattr(settings, "OPENAI_TIMEOUT", 120.0)
OPENAI_LONG_TIMEOUT = getattr(settings, "OPENAI_LONG_TIMEOUT", 380.0)
OPENAI_MODEL = settings.OPENAI_MODEL
OPENAI_TEMPERATURE = getattr(settings, "OPENAI_TEMPERATURE", 0.2)
```

#### 2d. Module docstring

Add docstring explaining this is the OpenAI-compatible client, parallel to `ollama_client.py`.

---

### Step 3: Export new functions from `src/services/dialogue/__init__.py`

**File:** `src/services/dialogue/__init__.py`

Add imports and exports:

```python
from .openai_client import call_llm, stream_llm

__all__ = [
    # ... existing exports
    "call_llm",
    "stream_llm",
]
```

---

### Step 4: Wire provider selection in `src/services/dialogue_engine.py`

**File:** `src/services/dialogue_engine.py`

Modify `call_ollama()` method and `_generate_streaming_response()` to route based on `LLM_PROVIDER`.

#### 4a. Update `call_ollama()` method (line ~37)

```python
async def call_ollama(self, prompt: str, model: str | None = None, language: str | None = None) -> str:
    """Delegate to the configured LLM provider."""
    if settings.LLM_PROVIDER == "openai":
        from src.services.dialogue import call_llm
        return await call_llm(prompt, model, language)
    else:
        from src.services.dialogue import call_ollama
        return await call_ollama(prompt, model, language)
```

#### 4b. Update `_generate_streaming_response()` method (line ~419)

Where it calls `stream_ollama()`, add provider routing:

```python
from src.services.dialogue import stream_ollama, stream_llm

# ... in the English path:
if settings.LLM_PROVIDER == "openai":
    gen = stream_llm(prompt, model=None, language=user_lang)
else:
    gen = stream_ollama(prompt, model=None, language=user_lang)

# ... in the non-English translation path:
if settings.LLM_PROVIDER == "openai":
    gen = stream_llm(translation_prompt, None, user_lang)
else:
    gen = stream_ollama(translation_prompt, None, user_lang)
```

#### 4c. Update imports at top of file

Add `stream_llm` to the existing import:

```python
from src.services.dialogue import (
    stream_ollama,
    stream_llm,  # NEW
)
```

---

### Step 5: Wire provider selection in `src/language/translation_service.py`

**File:** `src/language/translation_service.py`

The `translate_text()` function already accepts an `ollama_callable` parameter. No changes needed here — the caller (`dialogue_engine.py`) passes `self.call_ollama` which now routes to the right provider.

However, update the import to be neutral:

```python
# Change from:
from src.services.dialogue.ollama_client import call_ollama

# To (optional, for consistency):
from src.services.dialogue import call_ollama  # now routes based on provider
```

---

### Step 6: Wire provider selection in `src/language/language_service.py`

**File:** `src/language/language_service.py`

Line ~233-235 has a direct import of `call_ollama`. Update to use the routed version:

```python
# Change from:
from src.services.dialogue.ollama_client import call_ollama

# To:
from src.services.dialogue import call_ollama  # routes based on LLM_PROVIDER
```

---

### Step 7: Wire provider selection in `src/lessons/practice_extractor.py`

**File:** `src/lessons/practice_extractor.py`

Line ~50-53 has a direct import. Update:

```python
# Change from:
from src.services.dialogue.ollama_client import call_ollama

# To:
from src.services.dialogue import call_ollama  # routes based on LLM_PROVIDER
```

---

### Step 8: Wire provider selection in `src/scheduler/schedule_handlers.py`

**File:** `src/scheduler/schedule_handlers.py`

Line ~24 has `call_ollama` imported. It's passed to `translate_text()` as `ollama_callable`. Update import:

### Step 8b: Verify `prompt_builder.py` needs no changes

**File:** `src/language/prompt_builder.py` — **NO CHANGES NEEDED**

This file only builds prompt text (strings). It never calls the LLM directly. The prompt it builds is passed to `stream_ollama()` / `stream_llm()` in `dialogue_engine.py`, which already handles provider routing. Verified: zero imports of `ollama_client` or LLM call functions in this file.

```python
# Change from:
from src.services.dialogue.ollama_client import call_ollama

# To:
from src.services.dialogue import call_ollama  # routes based on LLM_PROVIDER
```

---

### Step 9: Update `OLLAMA_TIMEOUT` / `OLLAMA_LONG_TIMEOUT` defaults in config

**File:** `src/config.py`

The existing `OLLAMA_TIMEOUT` and `OLLAMA_LONG_TIMEOUT` are referenced in `ollama_client.py` via `getattr`. No change needed — they already exist. Just ensure the new OpenAI timeouts have sensible defaults.

---

### Step 10: Add test mock support for OpenAI client

**File:** `tests/mocks/ollama_mock.py` → **rename to** `tests/mocks/llm_mock.py` (**NEW**)

Create a new mock that can patch both Ollama and OpenAI clients:

```python
class LLMClientMock:
    """Mock for both Ollama and OpenAI LLM clients."""
    
    async def mock_call(self, prompt, model=None, language=None):
        # Same logic as existing OllamaMock._mock_call
    
    async def mock_stream(self, prompt, model=None, language=None):
        # Same logic as existing OllamaMock._mock_stream
    
    def patch_ollama(self, monkeypatch):
        # Patch ollama_client.call_ollama and stream_ollama
    
    def patch_openai(self, monkeypatch):
        # Patch openai_client.call_llm and stream_llm
```

Keep the existing `OllamaMock` class as-is for backward compatibility with all existing tests.

---

### Step 11: Write unit tests for OpenAI client

**File:** `tests/unit/services/test_openai_client.py` (**NEW**)

Test:
1. `call_llm()` returns correct text from mock OpenAI response
2. `call_llm()` handles API errors gracefully (returns error message)
3. `stream_llm()` yields tokens correctly from mock SSE stream
4. `stream_llm()` falls back to non-streaming on error
5. Test env short-circuit works
6. Config defaults are correct (temperature, timeout, model)

Use `unittest.mock.patch` to mock `openai.AsyncOpenAI` — no real API calls.

---

### Step 12: Write integration test for provider switching

**File:** `tests/unit/services/test_provider_routing.py` (**NEW**)

Test:
1. `DialogueEngine.call_ollama()` routes to Ollama when `LLM_PROVIDER=ollama`
2. `DialogueEngine.call_ollama()` routes to OpenAI when `LLM_PROVIDER=openai`
3. `_generate_streaming_response()` uses correct stream function based on provider

Use monkeypatch to verify the correct function is called.

---

### Step 13: Verify all existing tests still pass

Run the full test suite:

```bash
npm test
```

All existing tests should pass unchanged. The Ollama mock infrastructure handles test isolation.

---

### Step 14: Update `.env_template` with new settings

**File:** `.env_template`

Add commented-out OpenAI settings:

```bash
# OpenAI / OpenAI-compatible LLM provider
# LLM_PROVIDER=ollama          # "ollama" | "openai"
# OPENAI_API_KEY=sk-...
# OPENAI_BASE_URL=              # Empty = OpenAI; set for compatible servers
# OPENAI_MODEL=gpt-4o
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/config.py` | Add 7 new settings (OPENAI_*, LLM_PROVIDER) |
| `src/services/dialogue/openai_client.py` | **NEW** — OpenAI-compatible client (parallel to ollama_client.py) |
| `src/services/dialogue/__init__.py` | Export `call_llm`, `stream_llm` |
| `src/services/dialogue_engine.py` | Wire provider routing in `call_ollama()` and `_generate_streaming_response()` |
| `src/language/translation_service.py` | Update import to use routed `call_ollama` |
| `src/language/language_service.py` | Update import to use routed `call_ollama` |
| `src/lessons/practice_extractor.py` | Update import to use routed `call_ollama` |
| `src/scheduler/schedule_handlers.py` | Update import to use routed `call_ollama` |
| `src/language/prompt_builder.py` | **No changes** — only builds text strings, never calls LLM |
| `tests/mocks/llm_mock.py` | **NEW** — unified mock for both providers |
| `tests/unit/services/test_openai_client.py` | **NEW** — unit tests for OpenAI client |
| `tests/unit/services/test_provider_routing.py` | **NEW** — routing tests |
| `.env_template` | Add OpenAI settings (commented) |

**Total new files: 3**
**Total modified files: 7**
**Lines of new code: ~350-400** (mostly in openai_client.py)

---

## Design Decisions

1. **Additive only** — No refactoring of `ollama_client.py`. It stays exactly as-is.
2. **Parallel function names** — New functions are `call_llm()` / `stream_llm()` (not `call_openai()` / `stream_openai()`) so they can be unified later if desired.
3. **Provider routing at dialogue_engine level** — Minimal changes, easy to follow. Each caller just needs their import updated to use the routed version.
4. **OpenAI SDK** — Uses `openai.AsyncOpenAI` (already installed) instead of raw httpx for cleaner async streaming.
5. **Same error handling pattern** — OpenAI client returns the same `"[Sorry, I couldn't...]"` fallback as Ollama.
6. **Same test isolation** — Existing `OllamaMock` stays; new `LLMClientMock` supports both.
7. **`LLM_PROVIDER` defaults to `"ollama"`** — Zero impact on existing deployments.
8. **`OPENAI_BASE_URL` empty = OpenAI default** — Setting it enables any OpenAI-compatible server (local Pi server, Groq, Together, etc.).

---

## Implementation Notes

### Prompt Format Compatibility

The existing prompt builder (`src/language/prompt_builder.py`) builds a single text prompt with system instructions embedded. This works for both providers:
- **Ollama**: `{"prompt": "<full prompt>"}` — works as-is
- **OpenAI**: `{"messages": [{"role": "user", "content": "<full prompt>"}]}` — same content, just wrapped in messages array

No prompt changes needed.

### Function Calling Compatibility

The bot uses JSON-in-response function calling (not native tool calls). The prompt tells the LLM to return JSON like:
```json
{"response": "...", "functions": [...]}
```

This works identically on both providers — the LLM just needs to follow the prompt instructions. No changes to function calling needed.

### Streaming Filter Compatibility

`src/integrations/telegram_stream.py` parses the raw token stream for JSON prefix `{"response": "` and handles HTML buffering. This works regardless of which provider yields the tokens — the streaming filter is provider-agnostic.

### Timeout Differences

OpenAI SDK has a default 60s timeout. The `OPENAI_LONG_TIMEOUT` (380s) is needed for models that take longer (like `gpt-oss`). Set via `timeout` parameter in `AsyncOpenAI` constructor or per-request.

### Testing Strategy

- All existing tests use `OllamaMock` and `TEST_USE_REAL_OLLAMA` — they continue to work unchanged
- New tests mock `openai.AsyncOpenAI` directly
- Provider routing tests verify the correct function is called based on config
- No integration tests against real OpenAI API (use mocks)

---

## Post-Implementation Checklist

- [ ] All existing tests pass (`npm test`)
- [ ] New tests pass
- [ ] `ruff check src/ tests/` — 0 errors
- [ ] `.env_template` updated
- [ ] Manual test: switch `LLM_PROVIDER=openai`, verify bot responds
- [ ] Manual test: switch back to `LLM_PROVIDER=ollama`, verify bot still works

---

*Created: 2026-05-27*
