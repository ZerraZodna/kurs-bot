# Research: Prompt Builder Refactoring for OpenAI Integration

> **Goal**: Safely add OpenAI support while preserving Ollama functionality, function calling, and memory injection

---

## 🎯 **Objectives**

1. ✅ Add OpenAI support **without breaking** existing Ollama local/cloud functionality
2. ✅ Preserve **function calling** capabilities
3. ✅ Preserve **memory injection** (user profile, preferences, conversation history)
4. ✅ Maintain **backward compatibility** with existing callers
5. ✅ Create **comprehensive test strategy** (no test duplication)
6. ✅ Ensure **function calling** still works correctly

---

## 📊 **Current Architecture Analysis**

### Existing Flow (Ollama Local)

```
User Message
    ↓
DialogueEngine.process_message()
    ↓
PromptBuilder.build_prompt()
    ↓
Returns: SINGLE STRING (current format)
    ↓
ollama_client.stream_ollama(prompt_string)
    ↓
Returns: Streaming text chunks
```

### Current PromptBuilder Output

```python
# Current format (single string with -- section headers)
"""
[SYSTEM_PROMPT]

== Today's ACIM Lesson
[LESSON_CONTENT]

-- User Profile
[PROFILE_INFO]

-- Preferences
[PREFS]

-- Recent Conversation
User: [USER_1]
Assistant: [ASSISTANT_1]
User: [USER_2]
Assistant: [ASSISTANT_2]

-- Current Message
User: [CURRENT_INPUT]

Assistant:
"""
```

### Current Function Calling Flow

```python
# In prompt_builder.py line 151-155
if include_functions:
    function_context = self._build_function_context(context_type)
    if function_context:
        context_parts.append(f"\n\n{function_context}")
```

**Function context is INJECTED as text** into the prompt string, not structured.

### Current Memory Injection Flow

```python
# Memory injection happens in multiple methods:
# - _build_profile_context() (line 412)
# - _build_preferences_context() (line 441)
# - _build_conversation_history() (line 451)
# - _build_semantic_memory_context() (line 280)
```

**All memory is INJECTED as text sections** into the prompt string.

---

## 🚨 **Critical Concerns**

### 1. **Backward Compatibility**

**Problem**: All existing code expects `build_prompt()` to return a string

**Solution**:
- ✅ Keep `build_prompt()` unchanged (returns string)
- ✅ Add new method `build_messages()` (returns list of dicts)
- ✅ Default behavior remains the same
- ✅ Only callers who need OpenAI use `build_messages()`

### 2. **Function Calling Preservation**

**Current approach**: Function definitions injected as text into prompt string

**OpenAI requirement**: Native function calling with structured tools

**Options**:
- **Option A**: Keep text injection (works for Ollama local, may not work for OpenAI)
- **Option B**: Add structured function calling for OpenAI only
- **Option C**: Hybrid - text injection for both, but OpenAI can parse it better

**Recommendation**: **Option B** - Add structured function calling specifically for OpenAI

### 3. **Test Strategy**

**Problem**: Can't just delete old tests

**Solution**:
- ✅ Keep existing tests for `build_prompt()` (string format)
- ✅ Create NEW tests for `build_messages()` (structured format)
- ✅ Tests can share same logic, just different output expectations
- ✅ Use parameterized tests with format parameter

**Test naming**:
```python
# Existing tests (keep)
def test_build_prompt_includes_lesson():
    # Tests string format

# New tests (add)
def test_build_messages_includes_lesson():
    # Tests structured format
```

### 4. **Ollama Cloud vs Local**

**Current state**:
- Ollama Cloud: Uses `messages=[{"role": "user", "content": prompt}]` (line 132)
- Ollama Local: Uses `prompt` field (single string)

**Problem**: Ollama Cloud format is currently WRONG (uses simple user message, no system role)

**Solution**:
- Update Ollama Cloud to use structured format with system role
- This improves BOTH Ollama Cloud and OpenAI
- Ollama Local stays the same (backward compatible)

### 5. **Memory Injection Details**

**What needs to be preserved**:
- ✅ User profile (name, preferences, goals)
- ✅ Conversation history (user/assistant turns)
- ✅ Semantic memories (relevant context)
- ✅ Today's lesson (ACIM content)
- ✅ Function definitions (available tools)

**How to preserve**:
- Keep all memory injection logic in `build_messages()`
- Split into system message vs user message
- Conversation history becomes multiple user/assistant messages
- System prompt goes to system role
- Current input goes to user role

---

## 🔧 **Implementation Strategy**

### Phase 1: Add `build_messages()` Method

**Keep existing `build_prompt()` unchanged**

**Add new method**:

```python
class PromptBuilder:
    # Existing - keep unchanged
    def build_prompt(self, ...) -> str:
        # Current format with -- section headers
        pass

    # NEW - for OpenAI/Ollama Cloud
    def build_messages(
        self,
        user_id: int,
        user_input: str,
        system_prompt: str,
        include_lesson: bool = True,
        include_conversation_history: bool = True,
        history_turns: int = 4,
        relevant_memories: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "general_chat",
        include_functions: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Build structured messages for OpenAI/Ollama Cloud.

        Returns list of dicts with 'role' and 'content' keys.
        """
        messages = []

        # 1. System message (instructions)
        system_content = self._build_system_content(
            system_prompt=system_prompt,
            output_rules=self._build_channel_output_rules(user),
            include_lesson=include_lesson,
            include_functions=include_functions,
        )
        messages.append({
            "role": "system",
            "content": system_content
        })

        # 2. User context messages (can be multiple)
        context_messages = []

        # Add lesson if included
        if include_lesson:
            context_messages.append(self._build_lesson_message(user_id))

        # Add profile context
        profile_context = self._build_profile_context(user)
        if profile_context:
            context_messages.append({
                "role": "user",
                "content": f"\n-- User Profile\n{profile_context}"
            })

        # Add preferences
        prefs_context = self._build_preferences_context(user_id)
        if prefs_context:
            context_messages.append({
                "role": "user",
                "content": f"\n-- Preferences\n{prefs_context}"
            })

        # Add conversation history (multiple messages)
        if include_conversation_history:
            history_messages = self._build_conversation_history_messages(
                user_id, history_turns
            )
            messages.extend(history_messages)

        # Add semantic memories
        semantic_context = self._build_semantic_memory_context(relevant_memories or [])
        if semantic_context:
            context_messages.append({
                "role": "user",
                "content": f"\n-- Relevant Memories\n{semantic_context}"
            })

        # Add current user input
        current_message = {
            "role": "user",
            "content": f"\n-- Current Message\nUser: {user_input}"
        }

        # Combine all context into one user message or keep separate
        # Option A: Combine all into single user message
        # Option B: Keep as separate messages (better for context)

        return messages
```

### Phase 2: Update Ollama Cloud Client

**Current** (line 132):
```python
messages = [{"role": "user", "content": prompt}]  # Wrong! No system role
```

**New** (structured format):
```python
# Use build_messages for structured output
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": prompt}
]
```

### Phase 3: Update OpenAI Client

**New implementation**:
```python
async def call_openai(
    messages: List[Dict[str, str]],  # Already structured!
    model: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """Call OpenAI with pre-structured messages."""

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True  # For streaming
    )

    # Stream response
    full_response = ""
    async for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        full_response += delta
        yield delta

    return full_response
```

### Phase 4: Update DialogueEngine

**Current**:
```python
async def call_ollama(self, prompt: str, ...) -> str:
    return await call_ollama(prompt, ...)
```

**New** (support both formats):
```python
async def call_llm(
    self,
    messages: Union[str, List[Dict[str, str]]],  # Accept both!
    provider: str = "ollama",  # "ollama" or "openai"
    model: Optional[str] = None,
    ...
) -> str:
    """Unified LLM call supporting both Ollama and OpenAI."""

    if isinstance(messages, str):
        # Ollama local - use string format
        if provider == "ollama":
            return await ollama_client.call_ollama(messages, ...)
        else:
            # OpenAI with string - convert to structured
            structured = self.build_messages(...)
            return await openai_client.call(messages, ...)
    else:
        # Already structured - use for OpenAI or Ollama Cloud
        if provider == "openai":
            return await openai_client.call(messages, ...)
        elif provider == "ollama":
            return await ollama_client.call(messages, ...)
```

---

## 🧪 **Test Strategy**

### Existing Tests (Keep As-Is)

**These tests verify `build_prompt()` returns correct string format:**

```python
def test_build_prompt_includes_lesson():
    prompt = builder.build_prompt(user_id, user_input, system_prompt)
    assert "Today's ACIM Lesson" in prompt
    assert lesson_text in prompt

def test_build_prompt_includes_profile():
    prompt = builder.build_prompt(user_id, user_input, system_prompt)
    assert "User Profile" in prompt
    assert user_name in prompt
```

### New Tests (Add for `build_messages()`)

**These tests verify structured format:**

```python
def test_build_messages_returns_list():
    messages = builder.build_messages(user_id, user_input, system_prompt)
    assert isinstance(messages, list)
    assert len(messages) > 0

def test_build_messages_first_is_system():
    messages = builder.build_messages(user_id, user_input, system_prompt)
    assert messages[0]["role"] == "system"

def test_build_messages_includes_lesson():
    messages = builder.build_messages(user_id, user_input, system_prompt, include_lesson=True)
    # Check lesson is in one of the messages
    lesson_found = False
    for msg in messages:
        if "Today's ACIM Lesson" in msg["content"]:
            lesson_found = True
            break
    assert lesson_found

def test_build_messages_separates_user_and_assistant():
    messages = builder.build_messages(user_id, user_input, system_prompt,
                                      include_conversation_history=True, history_turns=2)
    # Should have multiple user/assistant messages
    user_count = sum(1 for m in messages if m["role"] == "user")
    assistant_count = sum(1 for m in messages if m["role"] == "assistant")
    assert user_count > 0
    assert assistant_count > 0
```

### Shared Test Infrastructure

**Use parameterized tests:**

```python
@pytest.mark.parametrize("format_type", ["string", "messages"])
def test_build_includes_lesson(format_type):
    if format_type == "string":
        result = builder.build_prompt(user_id, user_input, system_prompt)
    else:
        result = builder.build_messages(user_id, user_input, system_prompt)

    assert "Today's ACIM Lesson" in result
```

### Integration Tests

**Test end-to-end with both providers:**

```python
async def test_ollama_local_integration():
    # Use string format
    prompt = builder.build_messages(...)
    response = await ollama_client.call_ollama(prompt, ...)
    assert response is not None

async def test_openai_integration():
    # Use structured format
    messages = builder.build_messages(...)
    response = await openai_client.call(messages, ...)
    assert response is not None
```

---

## 📋 **Implementation Checklist**

### Phase 1: Add `build_messages()` Method
- [ ] Create `build_messages()` method signature
- [ ] Implement system message builder
- [ ] Implement lesson message builder
- [ ] Implement profile context builder
- [ ] Implement preferences builder
- [ ] Implement conversation history builder (multiple messages)
- [ ] Implement semantic memories builder
- [ ] Test with mock data

### Phase 2: Update Ollama Cloud Client
- [ ] Update cloud client to use structured messages
- [ ] Add system role to cloud messages
- [ ] Test with Ollama Cloud API
- [ ] Verify backward compatibility

### Phase 3: Create OpenAI Client
- [ ] Create `src/services/dialogue/openai_client.py`
- [ ] Implement `call_openai()` method
- [ ] Implement streaming support
- [ ] Add error handling
- [ ] Add function calling support (if needed)

### Phase 4: Update DialogueEngine
- [ ] Add `build_messages()` call to `DialogueEngine`
- [ ] Support both string and structured formats
- [ ] Add provider selection logic
- [ ] Update routing to use correct client

### Phase 5: Testing
- [ ] Keep existing tests unchanged
- [ ] Add new tests for `build_messages()`
- [ ] Add tests for OpenAI client
- [ ] Run full test suite
- [ ] Test with real OpenAI API

### Phase 6: Documentation
- [ ] Update `AGENTS.md` with new workflow
- [ ] Document OpenAI configuration
- [ ] Add migration guide
- [ ] Update README

---

## ⚠️ **Risk Mitigation**

### Risk 1: Breaking Existing Functionality

**Mitigation**:
- ✅ Keep `build_prompt()` unchanged
- ✅ All existing callers use `build_prompt()`
- ✅ Only new OpenAI callers use `build_messages()`
- ✅ Gradual rollout, not all at once

### Risk 2: Function Calling Breaks

**Mitigation**:
- ✅ Keep function injection in both methods
- ✅ Test function calling with both providers
- ✅ Ensure function definitions are properly formatted
- ✅ Add fallback for function calling errors

### Risk 3: Memory Injection Fails

**Mitigation**:
- ✅ Preserve all memory injection logic
- ✅ Test with various memory states
- ✅ Ensure semantic search still works
- ✅ Verify profile context is complete

### Risk 4: Tests Fail

**Mitigation**:
- ✅ Don't delete existing tests
- ✅ Add new tests with different names
- ✅ Use parameterized tests for shared logic
- ✅ Test both formats independently

### Risk 5: OpenAI API Rate Limits

**Mitigation**:
- [ ] Add rate limit monitoring
- [ ] Implement retry logic
- [ ] Add fallback to Ollama if OpenAI fails
- [ ] Set appropriate `max_tokens` limits

---

## 🎯 **Success Criteria**

- ✅ Ollama local still works (no breaking changes)
- ✅ Ollama Cloud uses structured format (improved)
- ✅ OpenAI integration works end-to-end
- ✅ Function calling works with both providers
- ✅ Memory injection works with both providers
- ✅ All existing tests pass
- ✅ New tests for `build_messages()` pass
- ✅ Documentation updated

---

## 📚 **References**

- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Function Calling Guide](https://platform.openai.com/docs/guides/gpt-function-calling)
- [Prompt Engineering Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)

---

*Last updated: Research in progress - awaiting implementation approval*
