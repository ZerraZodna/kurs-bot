import httpx
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.services.memory_manager import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.services.memory_extractor import MemoryExtractor
from src.config import settings

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"  # Default Ollama endpoint

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None
        self.memory_extractor = MemoryExtractor()

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
        
        Args:
            user_id: User ID from database
            text: User message
            session: SQLAlchemy session
            include_history: Include conversation history in context
            history_turns: Number of conversation turns to include
        
        Returns:
            AI response from Ollama
        """
        # Extract memories from user message using Ollama
        await self._extract_and_store_memories(user_id, text, session)
        
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

    async def _extract_and_store_memories(
        self, user_id: int, user_message: str, session: Session
    ) -> None:
        """
        Extract memories from user message and store them in the database.
        
        Args:
            user_id: User ID
            user_message: The user's message text
            session: SQLAlchemy session
        """
        try:
            # Get user's existing memories for context
            user_context = None
            if self.memory_manager:
                existing_memories = {}
                for key in ["learning_goal", "preferred_lesson_time", "first_name"]:
                    memory_items = self.memory_manager.get_memory(user_id, key)
                    if memory_items:
                        existing_memories[key] = memory_items[0].get("value")
                user_context = {"existing_memories": existing_memories}
            
            # Extract memories using Ollama
            extracted_memories = await MemoryExtractor.extract_memories(
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
