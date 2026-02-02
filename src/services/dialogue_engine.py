import httpx
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from langdetect import detect, LangDetectException
from src.services.memory_manager import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.services.memory_extractor import MemoryExtractor
from src.services.onboarding_service import OnboardingService
from src.services.scheduler import SchedulerService
from src.config import settings

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"  # Default Ollama endpoint

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None
        self.memory_extractor = MemoryExtractor()
        self.onboarding = OnboardingService(db) if db else None

    async def call_ollama(self, prompt: str, model: Optional[str] = None) -> str:
        model = model or settings.OLLAMA_MODEL
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "[No response from Ollama]")
        except Exception as e:
            logger.error(f"[Ollama error] {e}")
            return "[Sorry, I couldn't process your request right now.]"

    async def process_message(
        self,
        user_id: int,
        text: str,
        session: Session,
        include_history: bool = True,
        history_turns: int = 4,
    ) -> str:
        """
        Process user message with full context awareness.
        
        Automatically extracts and stores memories from the user message.
        Handles onboarding flow and schedule creation.
        
        Args:
            user_id: User ID from database
            text: User message
            session: SQLAlchemy session
            include_history: Include conversation history in context
            history_turns: Number of conversation turns to include
        
        Returns:
            AI response from Ollama
        """
        # FIRST: Extract memories from user message (this might store commitment, name, time, etc.)
        await self._extract_and_store_memories(user_id, text, session)
        
        # Check if user is requesting schedule/reminder setup (EXPLICIT REQUEST ONLY)
        if self.onboarding and self.onboarding.detect_schedule_request(text):
            schedule_response = await self._handle_schedule_request(user_id, text, session)
            if schedule_response:
                return schedule_response
        
        # Check if user needs onboarding (new users)
        if self.onboarding and self.onboarding.should_show_onboarding(user_id):
            onboarding_response = await self._handle_onboarding(user_id, text, session)
            if onboarding_response:
                return onboarding_response
        
        # Regular conversation
        if not self.prompt_builder:
            # Fallback for cases without DB session
            prompt = f"{settings.SYSTEM_PROMPT}\nUser: {text}\n\nAssistant:"
        else:
            # Build context-aware prompt
            prompt = self.prompt_builder.build_prompt(
                user_id=user_id,
                user_input=text,
                system_prompt=settings.SYSTEM_PROMPT,
                include_conversation_history=include_history,
                history_turns=history_turns,
            )
        
        # Call Ollama
        response = await self.call_ollama(prompt)
        
        return response

    async def _extract_and_store_memories(self, user_id: int, user_message: str, session: Session) -> None:
        """
        Extract meaningful information from user message and store as memories.
        
        Uses MemoryExtractor to intelligently identify facts, preferences, goals, etc.
        Automatically handles name, commitment, preferred times, etc.
        Also detects user's language from first message.
        
        Args:
            user_id: User ID from database
            user_message: The user's message
            session: SQLAlchemy session
        """
        try:
            # Detect language from user message (store on first message)
            if self.memory_manager:
                existing_lang = self.memory_manager.get_memory(user_id, "user_language")
                if not existing_lang:
                    try:
                        detected_lang = detect(user_message)
                        
                        # Check for Norwegian-specific keywords if confidence is low
                        norwegian_keywords = ["hei", "jeg", "heter", "jeg heter", "hvordan", "hvordan går", "takk", "vær så snill", "lyst"]
                        msg_lower = user_message.lower()
                        
                        # If Norwegian keywords found and message is short, prioritize Norwegian
                        if detected_lang in ['de', 'sv', 'da'] and len(user_message.split()) <= 5:
                            if any(kw in msg_lower for kw in norwegian_keywords):
                                detected_lang = 'no'
                        
                        # Map language codes to full names
                        lang_names = {
                            'no': 'Norwegian',
                            'en': 'English',
                            'sv': 'Swedish',
                            'da': 'Danish',
                            'de': 'German',
                            'fr': 'French',
                            'es': 'Spanish',
                            'it': 'Italian',
                            'pt': 'Portuguese',
                            'ru': 'Russian',
                            'ja': 'Japanese',
                            'zh-cn': 'Chinese',
                        }
                        lang_name = lang_names.get(detected_lang, detected_lang.upper())
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="user_language",
                            value=lang_name,
                            confidence=0.9,
                            source="dialogue_engine_language_detection",
                            category="preference",
                        )
                        logger.info(f"Detected language for user {user_id}: {lang_name} (code: {detected_lang})")
                    except LangDetectException as e:
                        logger.warning(f"Could not detect language: {e}")
            
            # Get user's existing memories for context
            user_context = None
            if self.memory_manager:
                existing_memories = {}
                for key in ["first_name", "acim_commitment", "learning_goal"]:
                    memories = self.memory_manager.get_memory(user_id, key)
                    if memories:
                        existing_memories[key] = memories[0].get("value")
                
                user_context = {
                    "user_id": user_id,
                    "existing_memories": existing_memories,
                } if existing_memories else None
            
            # Extract memories using Ollama
            extracted_memories = await self.memory_extractor.extract_memories(
                user_message, 
                user_context
            )
            
            # Store extracted memories
            for memory in extracted_memories:
                try:
                    self.memory_manager.store_memory(
                        user_id=user_id,
                        key=memory.get("key"),
                        value=memory.get("value"),
                        confidence=memory.get("confidence", 1.0),
                        ttl_hours=memory.get("ttl_hours"),
                        source="dialogue_engine_extractor",
                    )
                    logger.info(
                        f"Stored memory for user {user_id}: {memory.get('key')}="
                        f"{memory.get('value')[:50]}"
                    )
                except Exception as e:
                    logger.error(f"Error storing memory: {e}")
        
        except Exception as e:
            logger.error(f"Error in memory extraction: {e}")

    async def _handle_onboarding(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle onboarding flow.
        
        Onboarding just collects basic info (name, commitment).
        It does NOT create schedules - that only happens on explicit user request.
        
        Returns:
            Onboarding response or None if not in onboarding flow
        """
        status = self.onboarding.get_onboarding_status(user_id)
        
        # If onboarding just completed, show welcome message
        if status["onboarding_complete"]:
            # Check if this is the first message after completion
            if status["has_name"] and status["has_commitment"]:
                commit_memories = self.memory_manager.get_memory(user_id, "acim_commitment")
                # If commitment was just stored (check if it's recent), show completion message
                if commit_memories:
                    return self.onboarding.get_onboarding_complete_message(user_id)
            return None
        
        # If they're answering commitment question, check for affirmative
        if status["has_name"] and not status["has_commitment"]:
            if self.onboarding.detect_commitment_keywords(text):
                # User committed! (memory already stored by extractor)
                # Check that it was actually stored
                commit_memories = self.memory_manager.get_memory(user_id, "acim_commitment")
                if commit_memories:
                    logger.info(f"User {user_id} expressed interest in ACIM lessons")
                    # Return completion message
                    return self.onboarding.get_onboarding_complete_message(user_id)
        
        # Return next onboarding prompt
        return self.onboarding.get_onboarding_prompt(user_id)

    async def _handle_schedule_request(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle explicit schedule/reminder requests.
        
        Returns:
            Schedule setup response or None
        """
        # Check if user already has commitment
        status = self.onboarding.get_onboarding_status(user_id)
        
        if not status["has_commitment"]:
            # Need commitment first
            return self.onboarding.get_onboarding_prompt(user_id)
        
        # Check if they already have a schedule
        schedules = SchedulerService.get_user_schedules(user_id)
        if schedules:
            schedule = schedules[0]
            hour, minute = schedule.next_send_time.hour, schedule.next_send_time.minute
            return f"""You're already all set up! ✨

You have a daily reminder for {hour:02d}:{minute:02d} UTC.

Would you like to:
• Change the time?
• Add another reminder?
• Cancel the current reminder?"""

        # Check if they have a preferred time stored
        time_memories = self.memory_manager.get_memory(user_id, "preferred_lesson_time")

        if not time_memories:
            # Ask for their preferred time
            return """Great! I'll set up daily reminders for your ACIM lessons.

When would you like to receive them? (e.g., "9:00 AM", "morning", "evening", "8:30 PM")"""

        # They have a time preference - create the schedule
        time_str = time_memories[0]["value"]

        try:
            schedule = SchedulerService.create_daily_schedule(
                user_id=user_id,
                lesson_id=None,
                time_str=time_str,
                session=session,
            )

            hour, minute = SchedulerService.parse_time_string(time_str)

            name_memories = self.memory_manager.get_memory(user_id, "first_name")
            name = name_memories[0]["value"] if name_memories else "friend"

            return f"""Perfect, {name}! ✨

I've scheduled your daily ACIM lesson for {hour:02d}:{minute:02d} UTC each day.

Each day at this time, I'll send you one lesson. Remember: consistency is key. Even if you can only spend 5 minutes with the lesson, that daily practice will transform your perception.

Your first lesson will arrive tomorrow at {hour:02d}:{minute:02d} UTC. 🙏"""

        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return "I had trouble setting up your schedule. Could you tell me your preferred time? (e.g., '9:00 AM' or 'morning')"

    def get_conversation_state(self, user_id: int, session: Session) -> Dict[str, Any]:
        """
        Return current user memory and profile for conversation context.
        """
        if not self.memory_manager or not self.prompt_builder:
            return {}
        
        return {
            "user_id": user_id,
            "profile": {
                "goals": self.memory_manager.get_memory(user_id, "learning_goal"),
                "preferences": self.memory_manager.get_memory(user_id, "preferred_tone"),
            },
            "recent_history": self.prompt_builder._build_conversation_history(user_id, num_turns=3),
        }

    def set_conversation_state(self, user_id: int, state: Dict[str, Any], session: Session):
        """
        Update conversation context for multi-turn dialogue.
        Stores key insights and state in memory system.
        """
        if not self.memory_manager:
            return
        
        # Store state snapshots in memory if needed
        # Example: persist current lesson or topic
        if "current_topic" in state:
            self.memory_manager.store_memory(
                user_id=user_id,
                key="conversation_state",
                value=state["current_topic"],
                source="dialogue_engine",
                ttl_hours=24,  # 24-hour window for active conversation
                category="conversation",
            )

    def get_onboarding_prompt(self) -> str:
        """
        Return onboarding prompt sequence for new users.
        """
        if not self.prompt_builder:
            return "Welcome! What's your name?"
        
        return self.prompt_builder.build_onboarding_prompt(settings.SYSTEM_PROMPT)
