# TODO: Improve ACIM Bot Onboarding Flow

## Objective
Redesign the post-commitment onboarding message to be more structured and coach-led, following ACIM spiritual coaching principles.

## Problem
After commitment, the bot sends an informative message about scheduling/chat/lessons and ends with the open question "How would you like to begin?" This is too passive for new users who don't know what to do.

## Solution
Add a new onboarding step to ask if user is new or continuing, then immediately deliver the appropriate lesson with context.

---

## Implementation Steps

### Step 1: Update `get_onboarding_status()` method
**File:** `src/services/onboarding_service.py`

- Add check for "lesson_status_known" or "current_lesson" memory
- Update the onboarding_complete condition to include lesson status
- Return lesson_status in the status dict

**Changes needed:**
```python
# After checking commitment, add:
lesson_status_memories = self.memory_manager.get_memory(user_id, "current_lesson")
has_lesson_status = bool(lesson_status_memories)

# Update onboarding_complete:
onboarding_complete = has_name and has_consent and has_commitment and has_lesson_status

# Add to return dict:
"has_lesson_status": has_lesson_status,
```

### Step 2: Update `get_onboarding_prompt()` method
**File:** `src/services/onboarding_service.py`

Add "lesson_status" as a new onboarding step after "commitment".

**Add to prompts dict:**
```python
"Norwegian": {
    "name": "Velkommen! Jeg er din åndelige veileder for A Course in Miracles. Hva heter du?",
    "consent": "Før vi fortsetter: Er det greit at jeg lagrer samtalen og relevant informasjon for å gi deg oppfølging? (ja/nei)",
    "commitment": f"Herlig, {name}! Er du interessert i å utforske disse leksjonene sammen med meg? Jeg er her for å veilede og støtte deg på denne åndelige reisen.",
    "lesson_status": f"Flott, {name}! Er du ny til ACIM, eller har du allerede begynt med leksjonene?"
},
"English": {
    "name": "Welcome! I'm your spiritual coach for A Course in Miracles. What's your name?",
    "consent": "Before we continue: Do you consent to me storing the conversation and relevant info to support you? (yes/no)",
    "commitment": f"Beautiful, {name}! Are you interested in exploring these lessons together? I'm here to guide and support you on this journey.",
    "lesson_status": f"Wonderful, {name}! Are you new to ACIM, or have you already begun working with the lessons?"
}
```

**Add handling for lesson_status step:**
```python
elif next_step == "lesson_status":
    self.memory_manager.store_memory(
        user_id=user_id,
        key="onboarding_step_pending",
        value="lesson_status",
        category="conversation",
        ttl_hours=2,
        source="onboarding_service",
        allow_duplicates=False,
    )
    return lang_prompts["lesson_status"]
```

### Step 3: Create handler method for lesson status responses
**File:** `src/services/onboarding_service.py`

Add new method:
```python
def handle_lesson_status_response(self, user_id: int, text: str) -> Dict[str, Any]:
    """
    Handle user's response about whether they're new or continuing.
    
    Returns:
        Dict with action: "send_lesson_1" or "ask_lesson_number" and appropriate message
    """
    text_lower = text.lower().strip()
    
    # Detect "new" responses
    new_keywords = [
        "new", "ny", "beginner", "nybegynner", "start", "beginning", 
        "never", "aldri", "first time", "første gang"
    ]
    is_new = any(kw in text_lower for kw in new_keywords)
    
    # Detect "continuing" responses
    continuing_keywords = [
        "continuing", "fortsetter", "already", "allerede", "started", "begynt",
        "on lesson", "på leksjon", "lesson", "leksjon"
    ]
    is_continuing = any(kw in text_lower for kw in continuing_keywords)
    
    # Check if they mentioned a lesson number directly
    import re
    lesson_match = re.search(r'(?:lesson|leksjon)\s*(\d+)', text_lower)
    if lesson_match:
        lesson_num = int(lesson_match.group(1))
        if 1 <= lesson_num <= 365:
            return {"action": "send_specific_lesson", "lesson_id": lesson_num}
    
    if is_new:
        return {"action": "send_lesson_1"}
    elif is_continuing:
        return {"action": "ask_lesson_number"}
    
    # Unclear response - ask again more clearly
    return {"action": "clarify"}
```

### Step 4: Update dialogue_engine.py to handle lesson status
**File:** `src/services/dialogue_engine.py`

In the `_handle_onboarding()` method, after commitment is handled, check for lesson_status step:

```python
# After commitment handling, add:
pending_step = self.memory_manager.get_memory(user_id, "onboarding_step_pending")
if pending_step and pending_step[0].get("value") == "lesson_status":
    response = self.onboarding.handle_lesson_status_response(user_id, text)
    
    if response["action"] == "send_lesson_1":
        # Mark as starting from lesson 1
        self.memory_manager.store_memory(
            user_id=user_id,
            key="current_lesson",
            value="1",
            category="progress",
            confidence=1.0,
            source="onboarding_lesson_status",
        )
        
        # Get lesson 1 and send it with welcoming context
        lesson = session.query(Lesson).filter(Lesson.lesson_id == 1).first()
        if lesson:
            language = self._get_user_language(user_id)
            welcome_msg = self.onboarding.get_lesson_1_welcome_message(user_id)
            lesson_msg = await self._format_lesson_message(lesson, language)
            return f"{welcome_msg}\n\n{lesson_msg}"
    
    elif response["action"] == "send_specific_lesson":
        # They mentioned a specific lesson number
        lesson_id = response["lesson_id"]
        self.memory_manager.store_memory(
            user_id=user_id,
            key="current_lesson",
            value=str(lesson_id),
            category="progress",
            confidence=1.0,
            source="onboarding_lesson_status",
        )
        
        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if lesson:
            language = self._get_user_language(user_id)
            lesson_msg = await self._format_lesson_message(lesson, language)
            continuation_msg = self.onboarding.get_continuation_welcome_message(user_id, lesson_id)
            return f"{continuation_msg}\n\n{lesson_msg}"
    
    elif response["action"] == "ask_lesson_number":
        # Ask which lesson they're on
        language = self._get_user_language(user_id)
        if language == "Norwegian":
            return "Flott! Hvilken leksjon jobber du med nå?"
        else:
            return "Great! Which lesson are you currently working on?"
    
    elif response["action"] == "clarify":
        # Unclear response, ask again more directly
        language = self._get_user_language(user_id)
        if language == "Norwegian":
            return "Er du helt ny til ACIM, eller har du allerede begynt? (Svar 'ny' eller 'fortsetter')"
        else:
            return "Are you completely new to ACIM, or have you already started? (Answer 'new' or 'continuing')"
```

### Step 5: Add welcome message methods
**File:** `src/services/onboarding_service.py`

```python
def get_lesson_1_welcome_message(self, user_id: int) -> str:
    """Welcome message for brand new users starting with Lesson 1."""
    name_memories = self.memory_manager.get_memory(user_id, "first_name")
    if not name_memories:
        name_memories = self.memory_manager.get_memory(user_id, "name")
    name = name_memories[0]["value"] if name_memories else "friend"
    
    lang_memories = self.memory_manager.get_memory(user_id, "user_language")
    language = lang_memories[0]["value"] if lang_memories else "English"
    
    messages = {
        "Norwegian": f"""Perfekt, {name}! La oss begynne sammen med Leksjon 1. Dette er hvor transformasjonen starter.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere innsikter, stille spørsmål, eller reflektere sammen.

Ta deg tid med dagens leksjon. Når du er klar til å snakke om den, er jeg her. 🌿""",
        
        "English": f"""Perfect, {name}! Let's begin together with Lesson 1. This is where transformation starts.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss insights, ask questions, or reflect together.

Take your time with today's lesson. When you're ready to talk about it, I'm here. 🌿"""
    }
    
    return messages.get(language, messages["English"])

def get_continuation_welcome_message(self, user_id: int, lesson_id: int) -> str:
    """Welcome message for users continuing from a specific lesson."""
    name_memories = self.memory_manager.get_memory(user_id, "first_name")
    if not name_memories:
        name_memories = self.memory_manager.get_memory(user_id, "name")
    name = name_memories[0]["value"] if name_memories else "friend"
    
    lang_memories = self.memory_manager.get_memory(user_id, "user_language")
    language = lang_memories[0]["value"] if lang_memories else "English"
    
    messages = {
        "Norwegian": f"""Flott, {name}! Du er på Leksjon {lesson_id}. La oss fortsette reisen sammen.

📅 **Daglig støtte**: Hver morgen kl. 07:30 sender jeg deg neste leksjon.
💬 **Alltid tilgjengelig**: Du kan ta kontakt når som helst for å diskutere, stille spørsmål, eller reflektere.

Her er dagens leksjon:""",
        
        "English": f"""Wonderful, {name}! You're on Lesson {lesson_id}. Let's continue this journey together.

📅 **Daily support**: Each morning at 7:30 AM, I'll send you the next lesson.
💬 **Always available**: You can reach out anytime to discuss, ask questions, or reflect.

Here's today's lesson:"""
    }
    
    return messages.get(language, messages["English"])
```

---

## Testing Checklist

After implementing:

1. ✅ Reset database: `python scripts/reset_dev_db.py`
2. ✅ Test with name "Live" (short name fix)
3. ✅ Answer commitment: "Yes"
4. ✅ Answer lesson status: "I'm new" → Should get Lesson 1 immediately
5. ✅ Test again with: "I'm on lesson 5" → Should send lesson 5 with continuation message
6. ✅ Test unclear response → Should ask for clarification
7. ✅ Test direct mention: "I'm on lesson 123" → Should detect and send lesson 123

---

## Key Principles Applied

1. **Structure creates safety** - Clear direction, not passive waiting
2. **Immediate value** - Send lesson right away
3. **Establish rhythm** - Make daily delivery clear
4. **Companionship** - "Walking together" framing
5. **No ambiguity** - User knows exactly what happens next
