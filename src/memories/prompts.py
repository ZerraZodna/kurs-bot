"""Memory extraction prompts for AI Judge."""

# Combined extraction + validation + conflict detection prompt
MEMORY_EXTRACTION_JUDGE_PROMPT = """You are a personal memory system. Extract facts from user messages, validate their quality, AND detect conflicts with existing memories.

EXTRACTION RULES:
1. Extract explicit facts: name, goals, preferences, commitments
2. Store long-term goals, learning objectives, personal preferences
3. Only store sensitive info with explicit consent
4. Skip casual chit-chat, questions, vague statements
5. Work in any language - Norwegian, English, etc.
6. Prefer user corrections over inferred information

COMMON KEYS:
- "first_name": User's first/given name (ALWAYS use this key for any name)
- "learning_goal": What they want to learn/achieve
- "preferred_lesson_time": When they want lessons (morning, evening, 9:00 AM, etc.)
- "acim_commitment": Commitment to ACIM lessons
- "current_lesson": Lesson number they're on (numeric)
- "lesson_completed": Lesson number they finished (numeric)
- "email": Email address
- "phone": Phone number
- "birth_date": User's birth date. When you detect an explicit birth date, store it under this key.
    - Prefer ISO 8601 date format (YYYY-MM-DD) in the `value` when possible.
    - Accept and parse common formats such as `DD.MM.YYYY`, `D M YYYY`, `Month D, YYYY`, `YYYY-MM-DD`.
    - Example: "I was born on 23.05.1966" -> {{"key": "birth_date", "value": "1966-05-23", "confidence": 0.98}}

VALIDATION RULES:
- quality_score: 0.0-1.0 based on clarity and certainty
- cleaned_value: extract just the fact, remove extra text
- should_store: false if corrupted, nonsensical, or already known
- Reject values like "No, my full name is spelled backwards sennahoJ" -> cleaned: "Johannes"

CONFLICT DETECTION RULES:
When existing memories are provided, detect conflicts:
- Same key, different value = CONFLICT (action: REPLACE)
- Same key, same value = no conflict needed (already stored)
- Different keys, same concept = CONFLICT (e.g., "preferred_time" vs "preferred_lesson_time")
- For each conflict, include: existing_memory_id, reason, action (REPLACE/KEEP_BOTH/MERGE/FLAG)

Output ONLY valid JSON:
{{
  "memories": [
    {{
      "key": "first_name",
      "value": "raw extracted value",
      "cleaned_value": "cleaned value or null",
      "quality_score": 0.0-1.0,
      "should_store": true/false,
      "confidence": 0.0-1.0,
      "reasoning": "brief explanation",
      "conflicts": [
        {{
          "existing_memory_id": 123,
          "reason": "why this conflicts",
          "action": "REPLACE|KEEP_BOTH|MERGE|FLAG",
          "existing_value": "value of existing memory"
        }}
      ]
    }}
  ]
}}

Empty if nothing to store: {{"memories": []}}

User message: "{user_message}"
{context_str}"""


# Prompt for evaluating storage decisions (used by evaluate_storage)
STORAGE_EVALUATION_PROMPT = """You are a memory system judge. Evaluate this proposed memory storage.

USER MESSAGE: "{user_message}"

PROPOSED MEMORY:
  key: {proposed_key}
  value: {proposed_value}

EXISTING USER MEMORIES:
{memory_context}

Evaluate and respond in JSON:
{{
  "should_store": true/false,
  "quality_score": 0.0-1.0,
  "issues": ["list any problems"],
  "cleaned_value": "cleaned version or null",
  "conflicts": [
    {{
      "existing_memory_id": 123,
      "reason": "why this conflicts",
      "action": "REPLACE|KEEP_BOTH|MERGE|FLAG",
      "existing_value": "value of existing memory"
    }}
  ],
  "reasoning": "brief explanation"
}}

CRITICAL RULE - Single Memory Conflicts:
- If ANY active memory exists with the SAME key (regardless of value), this is a CONFLICT
- action=REPLACE when: same key with different value (update/correction)
- action=KEEP_BOTH when: same key but genuinely different facts (rare)
- When in doubt, use REPLACE for same-key conflicts

Rules:
- should_store=false if value is corrupted, nonsensical, or already known
- cleaned_value: extract just the fact if value contains extra text
- conflicts: ALWAYS include existing memories with the same key as conflicts
- action=REPLACE when new is correction/update
- action=KEEP_BOTH when genuinely different facts
- action=MERGE when combining gives better result
- action=FLAG when uncertain

Examples of conflicts:
- "first_name=Bob" vs "name=Robert" -> same person, different keys -> REPLACE
- "email=old@example.com" vs "email=new@example.com" -> same key, updated value -> REPLACE (same key!)
- "lesson_current=5" vs "lesson_completed=5" -> different concepts -> no conflict
- "preferred_lesson_time=07:30" vs "preferred_lesson_time=08:00" -> SAME KEY -> REPLACE

Examples of corrupted values:
- "No, my full name is spelled backwards sennahoJ" -> cleaned: "Johannes"
- "I think maybe around 5 or 6 lessons" -> cleaned: "5-6" or null"""


# Prompt for finding relevant memories
MEMORY_RELEVANCE_PROMPT = """Select memories relevant to this query.

QUERY: "{query}"
CONTEXT: "{context}"

MEMORIES:
{memory_context}

Return JSON:
{{
  "selected_ids": [123, 456],
  "reasoning": "why selected",
  "confidence": 0.0-1.0
}}

Select ALL memories that answer the query. If multiple conflict, select most recent."""

