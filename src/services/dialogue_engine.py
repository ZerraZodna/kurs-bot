import httpx
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.services.memory_manager import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.models.database import MessageLog
from src.config import settings
from datetime import datetime, timezone
import uuid

OLLAMA_URL = "http://localhost:11434/api/generate"  # Default Ollama endpoint

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None

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
            print("[Ollama error]", e)
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
        
        Args:
            user_id: User ID from database
            text: User message
            session: SQLAlchemy session
            include_history: Include conversation history in context
            history_turns: Number of conversation turns to include
        
        Returns:
            AI response from Ollama
        """
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
        
        # Log conversation if session available
        if session:
            self._log_conversation(user_id, text, response, session)
        
        return response
    
    def _log_conversation(self, user_id: int, user_text: str, assistant_text: str, session: Session) -> None:
        """Log user and assistant messages to message history."""
        thread_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        try:
            # Log user message
            user_msg = MessageLog(
                user_id=user_id,
                direction="inbound",
                channel="dialogue_engine",
                content=user_text,
                status="delivered",
                message_role="user",
                conversation_thread_id=thread_id,
                created_at=now,
            )
            session.add(user_msg)
            session.flush()
            
            # Log assistant response
            assistant_msg = MessageLog(
                user_id=user_id,
                direction="outbound",
                channel="dialogue_engine",
                content=assistant_text,
                status="delivered",
                message_role="assistant",
                conversation_thread_id=thread_id,
                created_at=now,
            )
            session.add(assistant_msg)
            session.commit()
        except Exception as e:
            print(f"[Error logging conversation] {e}")
            session.rollback()

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
