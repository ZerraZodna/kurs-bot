"""
Onboarding Service - Guide users through setup and commitment

Handles:
- 365 ACIM lesson commitment
- Preferred lesson time
- Schedule creation
- Multi-purpose reminder setup
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.services.memory_manager import MemoryManager
from src.models.database import User, Schedule
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class OnboardingService:
    """Manages user onboarding flow and commitment tracking."""
    
    def __init__(self, db: Session):
        self.db = db
        self.memory_manager = MemoryManager(db)
    
    def get_onboarding_status(self, user_id: int) -> Dict[str, Any]:
        """
        Check user's onboarding completion status.
        
        Onboarding is complete when we have:
        - User's name
        - Their interest/commitment to ACIM lessons
        
        Note: We DON'T automatically create schedules during onboarding.
        Schedules are only created when user explicitly requests reminders.
        
        Returns:
            Dict with onboarding_complete, steps_completed, next_step
        """
        # Check for key onboarding memories
        commitment_memories = self.memory_manager.get_memory(user_id, "acim_commitment")
        has_commitment = bool(commitment_memories)
        declined_commitment = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not interested"]
            for m in commitment_memories
        )
        # Check for name in either 'first_name' or 'name' key
        first_name_memories = self.memory_manager.get_memory(user_id, "first_name")
        name_memories = self.memory_manager.get_memory(user_id, "name")
        has_name = bool(first_name_memories or name_memories)
        
        # If we have 'name' but not 'first_name', copy it over
        if name_memories and not first_name_memories:
            self.memory_manager.store_memory(
                user_id=user_id,
                key="first_name",
                value=name_memories[0].get("value"),
                confidence=name_memories[0].get("confidence", 1.0),
                source="onboarding_service_name_migration",
                category="profile",
            )
        
        consent_memories = self.memory_manager.get_memory(user_id, "data_consent")
        has_consent = bool(consent_memories)
        declined_consent = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not consent"]
            for m in consent_memories
        )
        
        # Check for lesson status
        lesson_status_memories = self.memory_manager.get_memory(user_id, "current_lesson")
        has_lesson_status = bool(lesson_status_memories)
        
        steps_completed = []
        if has_name:
            steps_completed.append("name")
        if has_consent:
            steps_completed.append("consent")
        if has_commitment:
            steps_completed.append("commitment")
        if has_lesson_status:
            steps_completed.append("lesson_status")
        
        # Determine next step
        next_step = None
        if not has_name:
            next_step = "name"
        elif not has_consent:
            next_step = "consent"
        elif not has_commitment:
            next_step = "commitment"
        elif not has_lesson_status:
            next_step = "lesson_status"
        
        # Check if user has completed all onboarding steps
        onboarding_complete = has_name and has_consent and has_commitment and has_lesson_status

        # Return status dict
        return {
            "has_name": has_name,
            "has_consent": has_consent,
            "has_commitment": has_commitment,
            "has_lesson_status": has_lesson_status,
            "onboarding_complete": onboarding_complete,
            "steps_completed": steps_completed,
            "next_step": next_step,
            "declined_commitment": declined_commitment,
            "declined_consent": declined_consent,
        }
    
    def get_onboarding_prompt(self, user_id: int) -> Optional[str]:
        """
        Get the next onboarding prompt for the user in their language.
        
        Returns:
            Prompt string or None if onboarding complete
        """
        status = self.get_onboarding_status(user_id)
        
        if status["onboarding_complete"]:
            return None
        
        # Detect user's language
        lang_memories = self.memory_manager.get_memory(user_id, "user_language")
        language = lang_memories[0]["value"] if lang_memories else "English"
        
        next_step = status["next_step"]
        # Get name from either 'first_name' or 'name' key
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"
        
        # Prompts in different languages
        prompts = {
            "Norwegian": {
                "name": "Velkommen! Jeg er din åndelige veileder for A Course in Miracles. Hva heter du?",
                "consent": "Før vi fortsetter: Er det greit at jeg lagrer samtalen og relevant informasjon for å gi deg oppfølging? (ja/nei)",
                "commitment": f"""Herlig, {name}! 
Er du interessert i å utforske disse leksjonene sammen med meg? Jeg er her for å veilede og støtte deg på denne åndelige reisen.""",
                "lesson_status": f"Flott, {name}! Er du ny til ACIM, eller har du allerede begynt med leksjonene?"
            },
            "English": {
                "name": "Welcome! I'm your spiritual coach for A Course in Miracles. What's your name?",
                "consent": "Before we continue: Do you consent to me storing the conversation and relevant info to support you? (yes/no)",
                "commitment": f"""Beautiful, {name}! 
Are you interested in exploring these lessons together? I'm here to guide and support you on this journey.""",
                "lesson_status": f"Wonderful, {name}! Are you new to ACIM, or have you already begun working with the lessons?"
            },
        }
        
        # Get prompts for detected language, fall back to English
        lang_prompts = prompts.get(language, prompts["English"])
        
        if next_step == "name":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="name",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["name"]
        elif next_step == "consent":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="consent",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["consent"]
        elif next_step == "commitment":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="commitment",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["commitment"]
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
        
        return None
    
    def get_onboarding_complete_message(self, user_id: int) -> str:
        """
        Get the completion message after onboarding is done, in user's language.
        Also automatically creates a daily schedule at 07:30 AM.
        
        Returns:
            Welcome message explaining what the user can do next
        """
        # Get name from either 'first_name' or 'name' key
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"
        
        # Detect user's language
        lang_memories = self.memory_manager.get_memory(user_id, "user_language")
        language = lang_memories[0]["value"] if lang_memories else "English"
        
        # Automatically create daily schedule at 07:30 AM
        from src.services.scheduler import SchedulerService
        
        try:
            # Check if user already has an active schedule
            existing_schedules = self.db.query(Schedule).filter_by(
                user_id=user_id,
                is_active=True
            ).first()
            
            if not existing_schedules:
                # Create daily schedule at 07:30 AM
                SchedulerService.create_daily_schedule(
                    user_id=user_id,
                    lesson_id=None,  # Will send next lesson automatically
                    time_str="07:30",
                    schedule_type="daily",
                    session=self.db
                )
                logger.info(f"✓ Auto-created daily schedule at 07:30 AM for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to auto-create schedule for user {user_id}: {e}")
        
        # Messages in different languages
        messages = {
            "Norwegian": f"""Velkommen til vårt åndelige fellesskap, {name}! 🙏

Jeg er her for å støtte deg på reisen din med A Course in Miracles.

📅 **Daglige påminnelser satt opp** - Jeg vil sende deg leksjoner hver dag klokken 07:30. Du kan endre tiden når som helst.

Du kan også:
💬 **Chat med meg når som helst** - Still spørsmål, del innsikter eller diskuter leksjonene
📖 **Utforsk leksjoner** - Spør meg om noen av de 365 leksjonene når du er klar

Hvordan vil du begynne?""",
            "English": f"""Welcome to our spiritual community, {name}! 🙏

I'm here to support you on your journey with A Course in Miracles.

📅 **Daily reminders set up** - I'll send you lessons every day at 07:30 AM. You can change the time anytime.

You can also:
💬 **Chat with me anytime** - Ask questions, share insights, or discuss the lessons
📖 **Explore lessons** - Ask me about any of the 365 lessons whenever you're ready

How would you like to begin?""",
        }
        
        return messages.get(language, messages["English"])
    
    def is_user_new(self, user_id: int) -> bool:
        """Check if user is new (created within last 10 minutes)."""
        user = self.db.query(User).filter_by(user_id=user_id).first()
        if not user:
            return False
        
        # Check if created in last 10 minutes
        now = datetime.now(timezone.utc)
        time_diff = now - user.created_at.replace(tzinfo=timezone.utc)
        return time_diff.total_seconds() < 600  # 10 minutes
    
    def should_show_onboarding(self, user_id: int) -> bool:
        """
        Determine if we should show onboarding prompts.
        
        Returns:
            True if user needs onboarding
        """
        status = self.get_onboarding_status(user_id)
        
        # Show if not complete and user is relatively new (or never completed)
        if not status["onboarding_complete"]:
            if status.get("declined_consent") or status.get("declined_commitment"):
                return False
            return True
        
        return False
    
    def detect_commitment_keywords(self, message: str) -> bool:
        """
        Detect if user message indicates readiness to commit to lessons.
        
        Args:
            message: Users message text
        
        Returns:
            True if commitment keywords detected
        """
        message_lower = message.lower()
        
        commitment_keywords = [
            "yes", "yeah", "sure", "ready", "let's do it", "i'm in",
            "commit", "start", "begin", "sign me up", "i want to",
            "interested", "absolutely", "definitely", "ok", "okay",
            # Norwegian
            "ja", "jada", "klar", "begynn", "start", "vil gjerne",
            # Swedish
            "ja", "gärna", "redo", "börja",
            # Danish
            "ja", "gerne", "klar", "begynd",
            # German
            "ja", "klar", "bereit", "los geht's",
            # Spanish
            "sí", "si", "claro", "listo", "empecemos", "quiero",
            # French
            "oui", "d'accord", "prêt", "prete", "commençons", "commencer",
            # Portuguese
            "sim", "claro", "pronto", "vamos começar", "quero",
            # Italian
            "sì", "si", "certo", "pronto", "iniziamo", "voglio",
        ]
        
        return any(keyword in message_lower for keyword in commitment_keywords)

    def detect_decline_keywords(self, message: str) -> bool:
        """Detect if user declines ACIM or consent."""
        message_lower = message.lower()
        decline_keywords = [
            "no", "not interested", "no thanks", "no thank you", "stop",
            "don't want", "do not want", "not into", "leave me",
            # Norwegian
            "nei", "ikke interessert", "nei takk", "stopp",
            "vil ikke", "ønsker ikke",
        ]
        return any(keyword in message_lower for keyword in decline_keywords)

    def detect_consent_keywords(self, message: str) -> Optional[bool]:
        """Return True if consent given, False if declined, None if unclear."""
        message_lower = message.lower()
        yes_keywords = [
            "yes", "yeah", "sure", "ok", "okay", "i agree", "consent",
            # Norwegian
            "ja", "jada", "greit", "ok", "samtykker",
        ]
        no_keywords = [
            "no", "no thanks", "no thank you", "don't", "do not",
            # Norwegian
            "nei", "nei takk", "ikke",
        ]
        if any(k in message_lower for k in yes_keywords):
            return True
        if any(k in message_lower for k in no_keywords):
            return False
        return None
    
    def detect_schedule_request(self, message: str) -> bool:
        """
        Detect if user is asking for reminders/scheduling.
        
        Args:
            message: Users message text
        
        Returns:
            True if scheduling keywords detected
        """
        message_lower = message.lower()
        
        schedule_keywords = [
            "remind", "reminder", "schedule", "daily", "every day",
            "send me", "notify", "notification", "alert", "ping",
            # Norwegian
            "påminn", "minne", "hver dag", "daglig", "varsle",
        ]
        
        return any(keyword in message_lower for keyword in schedule_keywords)

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
