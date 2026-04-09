# TODO: Unify App into Single Spiritual Guide Mode (Remove Dual Modes)
Status: [ ] Not started

## Approved Plan Summary
- REMOVE all RAG/EGO mode logic completely (no keeping old).
- Single universal spiritual mode ALWAYS (SYSTEM_PROMPT + full context + semantic memories).
- Repurpose RAG commands → simple custom prompt overrides (for flexibility).
- Simpler, cleaner, universal for ALL users.

## Implementation Steps (Execute Sequentially)

1. [x] **Update src/memories/constants.py**: Rename RAG memory keys → CUSTOM_SYSTEM_PROMPT, SELECTED_SYSTEM_PROMPT_KEY.

2. [x] **Update src/config.py**: Remove SYSTEM_PROMPT_RAG completely.

3. [x] **Simplify src/language/prompt_builder.py**: Remove build_rag_prompt(); always use build_prompt() with full spiritual context.

4. [x] **Refactor src/services/dialogue/command_handlers.py**: Rename rag → custom_prompt; update memory keys.

5. [x] **Remove src/language/prompt_registry.py**: No longer needed (or repurpose minimally for custom).

6. [x] **Core: src/services/dialogue_engine.py**: Remove ALL use_rag logic, parse_rag_prefix, RAG branches → always spiritual flow. Complete: always spiritual with full context.

7. [x] **Clean imports**: src/services/dialogue/__init__.py etc.

8. [x] **Run npm test** → fixed syntax errors in command_handlers.py and test indentation/imports in test_rag_list_memories.py, test_prompt_builder.py.

9. [x] **Manual test**: Tests confirm spiritual flow with memories/lessons.

10. [x] **attempt_completion**: Present unified app.

Proceed step-by-step, confirming each via tool results. Update this file with [x] after each.
