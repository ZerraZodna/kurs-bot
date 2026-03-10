"""Memory extraction prompts for AI Judge."""

# Combined extraction + conflict detection prompt
MEMORY_EXTRACTION_JUDGE_PROMPT = """You are a personal memory system. Extract facts from user messages AND detect conflicts with existing memories.

EXTRACTION RULES:
1. Extract explicit facts: name, goals, preferences
2. Store long-term goals, learning objectives, personal preferences
3. Only store sensitive info with explicit consent
4. Skip casual chit-chat, questions, vague statements
5. Work in any language - Norwegian, English, etc.
6. Prefer user corrections over inferred information
7. ALWAYS extract explicit lesson progress statements like "I am on lesson X", "I'm on lesson X", "currently on lesson X" → store as current_lesson with value X

COMMON KEYS:
- "first_name": User's first/given name (ALWAYS use this key for any name)
- "preferred_lesson_time": When they want lessons (morning, evening, 9:00 AM, etc.)
- "current_lesson": Lesson number they're on (numeric 1-365) - EXTRACT from phrases like "I am on lesson 8", "I'm on lesson X", etc.
- "lesson_completed": Lesson number they finished (numeric)

OUTPUT FORMAT:
Output ONLY valid JSON with extracted memories. Include conflict info when existing memories are provided:
- Same key, different value = CONFLICT: Set archive_memory_ids to list of old memory IDs to archive
- Same key, same value = NO CONFLICT: Set archive_memory_ids to empty list []

{{
  "memories": [
    {{
      "key": "first_name",
      "value": "extracted value",
      "archive_memory_ids": [123, 456] or []
    }}
  ]
}}

Empty if nothing to store: {{"memories": []}}

User message: "{user_message}"
{context_str}"""

