import httpx
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.services.memory_manager import MemoryManager
from src.config import settings

OLLAMA_URL = "http://localhost:11434/api/generate"  # Default Ollama endpoint

class DialogueEngine:
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or MemoryManager()

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

    async def process_message(self, user_id: int, text: str, session: Session) -> str:
        """
        Send user message to Ollama and return the AI's response.
        """
        # Prepend system prompt for persona
        prompt = f"{settings.SYSTEM_PROMPT}\nUser: {text}"
        return await self.call_ollama(prompt)

    def get_conversation_state(self, user_id: int, session: Session) -> Dict[str, Any]:
        """
        Return current user memory and profile for conversation context.
        """
        # TODO: Query memory and user profile
        return {}

    def set_conversation_state(self, user_id: int, state: Dict[str, Any], session: Session):
        """
        Update conversation context for multi-turn dialogue.
        """
        # TODO: Update memory/profile as needed
        pass

    def get_onboarding_prompt(self, user_id: int, session: Session) -> str:
        """
        Return onboarding prompt sequence for new users.
        """
        # TODO: Implement onboarding flow
        return "Welcome! What's your name?"
