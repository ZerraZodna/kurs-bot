# Research: OpenAI Integration as Alternative to Ollama

> **Goal**: Research and document how to integrate OpenAI as an alternative LLM provider to Ollama in kurs-bot

---

## ✅ Phase 1: Current State Analysis (COMPLETE)

### Implementation Pattern
- **File**: `src/services/dialogue/ollama_client.py`
- **Key Functions**:
  - `call_ollama()` — Top-level async method (cloud/local routing)
  - `stream_ollama()` — Async generator for streaming responses
  - `_call_local_http()` — Local HTTP API calls (httpx)
  - `_cloud_call_sync()` — Cloud calls via official OllamaClient

### Configuration (src/config.py)
```python
OLLAMA_MODEL: str = "qwen3:latest"
OLLAMA_TEMPERATURE: float = 0.2
OLLAMA_API_KEY: str = ""
LOCAL_OLLAMA_URL: str = "http://localhost:11434/api/generate"
CLOUD_OLLAMA_URL: str = "https://ollama.com/api/generate"
OLLAMA_TIMEOUT: float = 120.0
OLLAMA_LONG_TIMEOUT: float = 380.0
```

### Integration Pattern
- **DialogueEngine** delegates to `call_ollama()`
- **Streaming**: Uses async HTTP streaming with httpx
- **Fallbacks**: Non-streaming fallback on errors
- **Test Environment**: `TEST_USE_REAL_OLLAMA` flag for CI

---

## 📊 Phase 2: OpenAI SDK Research (IN PROGRESS)

### OpenAI Python SDK Options

**Option A: Official OpenAI SDK** (Recommended)
- Library: `openai` (pip install openai)
- Pros: Official, well-documented, actively maintained
- Cons: Requires API key, different API structure

**Option B: Raw HTTP (like Ollama)**
- Pros: No external dependencies, more control
- Cons: Verbose, no streaming helpers, manual error handling

### OpenAI API Structure

**Chat Completions (Recommended)**
```python
import openai

client = openai.OpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
    ],
    stream=True  # For streaming support
)
for chunk in response:
    print(chunk.choices[0].delta.content)
```

**Text Completions (Legacy)**
```python
response = client.completions.create(
    model="gpt-3.5-turbo",
    prompt="Hello world",
    stream=True
)
```

### Key Differences from Ollama

| Feature | Ollama | OpenAI |
|---------|--------|--------|
| **API Endpoint** | `/api/generate` | `/v1/chat/completions` |
| **Message Format** | Flexible | Strict (system/user/assistant roles) |
| **Streaming** | Line-delimited JSON | SSE (Server-Sent Events) |
| **Auth** | Bearer token or none | API key in header |
| **Response** | JSON with `response` field | JSON with `choices[0].message.content` |
| **Timeouts** | Configurable per request | Default 60s (configurable) |

### OpenAI SDK Features

**Chat Completions API** (Primary)
- Supports system/user/assistant roles
- Function calling support
- Tool use patterns
- Better for chat applications

**Streaming Support**
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    stream=True
)
for chunk in response:
    content = chunk.choices[0].delta.content or ""
    yield content
```

**Response Object Structure**
```python
{
    "id": "chat-...",
    "choices": [{
        "delta": {"content": "Hello", "role": "assistant"},
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15
    }
}
```

---

## 🔧 Phase 3: Architecture Design (TO DO)

### Recommended Approach: Provider-Agnostic Adapter Layer

**Why this approach?**
- Reusable for multiple providers
- Easy to add more LLMs later
- Consistent interface
- Testable

**Design Pattern:**
```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

class BaseLLMClient(ABC):
    """Abstract base for all LLM clients."""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
    
    @abstractmethod
    async def call(self, prompt: str, temperature: float = 0.2) -> str:
        """Make non-streaming call."""
        pass
    
    @abstractmethod
    async def stream(self, prompt: str, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """Make streaming call."""
        pass

# Existing implementation
class OllamaClient(BaseLLMClient):
    # Already exists in ollama_client.py
    pass

# New implementation
class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        super().__init__(api_key, base_url, model)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    async def call(self, prompt: str, temperature: float = 0.2) -> str:
        # Implementation using chat.completions.create(stream=False)
        pass
    
    async def stream(self, prompt: str, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        # Implementation using chat.completions.create(stream=True)
        pass
```

### Integration Strategy

**Option 1: Unified Client with Provider Selection**
```python
# New file: src/services/dialogue/llm_client.py
class UnifiedLLMClient:
    def __init__(self, provider: str, settings):
        if provider == "ollama":
            self.client = OllamaClient(settings)
        elif provider == "openai":
            self.client = OpenAIClient(settings)
    
    async def call(self, prompt: str, **kwargs) -> str:
        return await self.client.call(prompt, **kwargs)
    
    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        async for token in self.client.stream(prompt, **kwargs):
            yield token
```

**Option 2: Keep Separate Clients (Current Ollama Pattern)**
```python
# Keep ollama_client.py as-is
# Create new: src/services/dialogue/openai_client.py

# Updated dialogue_engine.py:
from src.services.dialogue import ollama_client, openai_client

class DialogueEngine:
    async def call_llm(self, prompt: str, provider: str = "ollama", **kwargs) -> str:
        if provider == "openai":
            return await openai_client.call(prompt, **kwargs)
        return await ollama_client.call(prompt, **kwargs)
```

**Option 3: Configuration-Based Routing**
```python
# Read from .env: DEFAULT_LLM_PROVIDER=ollama or openai
# Automatically select provider based on settings
```

### Recommended: Option 1 (Unified Client)
**Benefits:**
- Single interface
- Easy switching between providers
- Consistent error handling
- Centralized logging
- Future-proof (easy to add more providers)

---

## 🔐 Phase 4: Configuration Design (TO DO)

### Proposed `.env` Additions
```bash
# OpenAI Settings
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1  # or custom endpoint
OPENAI_DEFAULT_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=2048

# Provider Selection
DEFAULT_LLM_PROVIDER=ollama  # or openai
```

### Settings Object Extension
```python
class Settings(BaseSettings):
    # Existing Ollama settings
    OLLAMA_MODEL: str = "qwen3:latest"
    OLLAMA_API_KEY: str = ""
    
    # New OpenAI settings
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2048
    
    # Provider selection
    DEFAULT_LLM_PROVIDER: str = "ollama"  # or "openai"
```

---

## 🧪 Phase 5: Testing Strategy (TO DO)

### Testing Approach
1. **Unit Tests**
   - Mock OpenAI API responses
   - Test client initialization
   - Test error handling

2. **Integration Tests**
   - Use OpenAI Playground sandbox
   - Compare output quality vs Ollama
   - Test streaming behavior

3. **End-to-End Tests**
   - Full message processing flow
   - Switch between providers
   - Error recovery tests

### OpenAI Sandbox
- OpenAI provides free testing credits
- Use `gpt-3.5-turbo` for cost-effective testing
- Playground: https://platform.openai.com/playground

---

## 📋 Phase 6: Implementation Checklist (TO DO)

### Prerequisites
- [ ] Install OpenAI SDK: `pip install openai`
- [ ] Set up OpenAI API key in `.env`
- [ ] Review OpenAI rate limits and pricing

### Implementation Steps
- [ ] Create `src/services/dialogue/openai_client.py`
- [ ] Implement `BaseLLMClient` abstract class
- [ ] Implement `OpenAIClient` class
- [ ] Add configuration to `src/config.py`
- [ ] Update `src/services/dialogue_engine.py` to support provider selection
- [ ] Add error handling and logging
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update documentation
- [ ] Add migration guide for users

### Documentation
- [ ] User guide: How to enable OpenAI
- [ ] Developer docs: Code structure
- [ ] Troubleshooting guide
- [ ] Cost comparison: OpenAI vs Ollama

---

## 💰 Phase 7: Cost Analysis (TO DO)

### OpenAI Pricing (as of research)
- **gpt-4o**: ~$0.005/1K tokens input, ~$0.015/1K tokens output
- **gpt-3.5-turbo**: ~$0.0005/1K tokens input, ~$0.0015/1K tokens output
- **Free tier**: 1000 free requests/month (for new users)

### Comparison with Ollama
- **Ollama (local)**: Free, no cost
- **Ollama Cloud**: ~$20-50/month depending on usage
- **OpenAI**: Pay-per-use, scales with usage

### Recommendation
- Use Ollama for local development (free)
- Use OpenAI for production (reliable, scalable)
- Allow users to switch based on needs

---

## 🎯 Next Steps

1. **Create Prototype Implementation** (`src/services/dialogue/openai_client.py`)
2. **Write Unit Tests**
3. **Test with OpenAI Sandbox**
4. **Document Implementation**
5. **Create Migration Guide**

---

## 📚 References

- [OpenAI Python SDK Documentation](https://python.openai.com/docs/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)
- [OpenAI Streaming](https://platform.openai.com/docs/guides/streaming)

---

*Last updated: Research in progress*
