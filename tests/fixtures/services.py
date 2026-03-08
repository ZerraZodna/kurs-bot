"""Service fixtures for tests."""

import datetime
from typing import Generator, Optional
from unittest.mock import MagicMock, AsyncMock

import pytest
from sqlalchemy.orm import Session

from src.memories import MemoryManager
from src.services.dialogue_engine import DialogueEngine
from src.scheduler import SchedulerService
from src.services.embedding_service import EmbeddingService
from src.models.database import Lesson
from tests.mocks.embedding_mock import _get_embedding_dim


@pytest.fixture
def lesson(db_session: Session) -> Lesson:
    """A basic lesson for testing."""
    lesson = Lesson(
        title="Test Lesson",
        content="This is test content for lesson 1.",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(lesson)
    db_session.commit()
    return lesson


@pytest.fixture
def memory_manager(db_session: Session) -> MemoryManager:
    """MemoryManager instance bound to test database."""
    return MemoryManager(db=db_session)


@pytest.fixture
def dialogue_engine(db_session: Session) -> DialogueEngine:
    """DialogueEngine instance bound to test database."""
    return DialogueEngine(db_session)


@pytest.fixture
def scheduler_service() -> Generator[SchedulerService, None, None]:
    """SchedulerService fixture with automatic cleanup.
    
    Initializes the scheduler before test and shuts down after.
    """
    SchedulerService.init_scheduler()
    yield SchedulerService
    SchedulerService.shutdown()


@pytest.fixture
def mock_embedding_service(monkeypatch) -> MagicMock:
    """Mocked EmbeddingService that returns zero vectors.
    
    Use this to avoid heavy ML dependencies in tests.
    Automatically detects dimension based on EMBEDDING_BACKEND config.
    """
    mock_service = MagicMock(spec=EmbeddingService)
    mock_service.embedding_dimension = _get_embedding_dim()
    
    # Mock async methods
    async def mock_generate_embedding(text: str) -> Optional[list]:
        if not text:
            return None
        return [0.0] * mock_service.embedding_dimension
    
    async def mock_batch_embed(texts: list) -> list:
        return [
            None if not t else [0.0] * mock_service.embedding_dimension
            for t in texts
        ]
    
    async def mock_close() -> None:
        pass
    
    mock_service.generate_embedding = AsyncMock(side_effect=mock_generate_embedding)
    mock_service.batch_embed = AsyncMock(side_effect=mock_batch_embed)
    mock_service.close = AsyncMock(side_effect=mock_close)
    
    # Patch the module
    import src.services.embedding_service as emb_module
    monkeypatch.setattr(emb_module, "get_embedding_service", lambda: mock_service)
    monkeypatch.setattr(emb_module, "_embedding_service", mock_service)
    
    return mock_service


@pytest.fixture
def mock_ollama_client(monkeypatch) -> MagicMock:
    """Mocked Ollama client for dialogue tests.
    
    Returns predictable JSON responses with function calls for memory extraction.
    """
    import json
    import re
    from src.memories.constants import MemoryKey
    mock_client = MagicMock()
    
    async def mock_call_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None) -> str:
        import sys
        prompt_lower = prompt.lower()
        
        # Simple debug: check if onboarding context exists
        has_onboarding = "Current step:" in prompt
        sys.stderr.write(f"\n[MOCK] Onboarding context present: {has_onboarding}\n")
        if has_onboarding:
            step_match = re.search(r'Current step:\s*(\w+)', prompt, re.IGNORECASE)
            if step_match:
                sys.stderr.write(f"[MOCK] Step found: {step_match.group(1)}\n")
        
        # Extract the last user message from the prompt
        # The prompt ends with: "-- Current Message\nUser: {user_input}\n\nAssistant:"
        user_msg = ""
        
        # Try to find in Current Message section - match up to \n\nAssistant:
        current_msg_match = re.search(r'-- Current Message\s*\n\s*User:\s*(.+?)(?:\n\nAssistant:|$)', prompt, re.IGNORECASE | re.DOTALL)
        if current_msg_match:
            user_msg = current_msg_match.group(1).strip()
        else:
            # Fallback: try to find last User: line in conversation history
            user_matches = re.findall(r'User:\s*(.+?)(?:\n|$)', prompt, re.IGNORECASE)
            if user_matches:
                user_msg = user_matches[-1].strip()
        
        user_msg_lower = user_msg.lower()
        
        # Check for onboarding context - look for "Next Onboarding Step" in prompt
        # Use simpler, more robust regex patterns
        current_step_match = re.search(r'Current step:\s*(\w+)', prompt, re.IGNORECASE)
        next_question_match = re.search(r'ask this next question:\s*"([^"]+)"', prompt, re.IGNORECASE)
        current_onboarding_step = current_step_match.group(1).lower() if current_step_match else None
        next_question = next_question_match.group(1) if next_question_match else None
        
        # For name extraction - check for "my name is X" pattern
        name_match = re.search(r'my\s+name\s+is\s+(\w+)', user_msg, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)
            # If we have a next onboarding question, include it in the response
            if next_question:
                return json.dumps({
                    "response": f"Nice to meet you, {name}! {next_question}",
                    "functions": [
                        {"name": "extract_memory", "parameters": {"key": MemoryKey.FIRST_NAME, "value": name, "confidence": 0.9}}
                    ]
                })
            return json.dumps({
                "response": f"Nice to meet you, {name}! I've noted your name.",
                "functions": [
                    {"name": "extract_memory", "parameters": {"key": MemoryKey.FIRST_NAME, "value": name, "confidence": 0.9}}
                ]
            })
        
        # For simple yes/no responses (name confirmation, consent, etc.)
        if user_msg_lower in ['yes', 'ja']:
            # Check context from prompt - use onboarding step if available
            if current_onboarding_step == "name" or "name" in prompt_lower:
                response_text = "Great! I'll use your name from Telegram."
                if next_question:
                    response_text += f" {next_question}"
                # Extract the name from the prompt (it should be in the user profile section)
                name_from_profile = None
                profile_match = re.search(r'User Profile\s*\n.*?Name:\s*(\w+)', prompt, re.IGNORECASE | re.DOTALL)
                if profile_match:
                    name_from_profile = profile_match.group(1)
                functions = [
                    {"name": "confirm_yes", "parameters": {"context": "use_telegram_name"}}
                ]
                if name_from_profile:
                    functions.append({
                        "name": "extract_memory",
                        "parameters": {"key": MemoryKey.FIRST_NAME, "value": name_from_profile, "confidence": 0.9}
                    })
                return json.dumps({
                    "response": response_text,
                    "functions": functions
                })
            if current_onboarding_step == "timezone" or "timezone" in prompt_lower:
                response_text = "Great! I'll set your timezone."
                if next_question:
                    response_text += f" {next_question}"
                return json.dumps({
                    "response": response_text,
                    "functions": [
                        {"name": "confirm_yes", "parameters": {"context": "timezone_inferred"}}
                    ]
                })
            if current_onboarding_step == "consent" or "consent" in prompt_lower:
                response_text = "Thank you! Your consent has been recorded."
                if next_question:
                    response_text += f" {next_question}"
                return json.dumps({
                    "response": response_text,
                    "functions": [
                        {"name": "confirm_yes", "parameters": {"context": "data_consent"}}
                    ]
                })
            # Generic yes
            return json.dumps({
                "response": "Great! I've noted that.",
                "functions": [
                    {"name": "confirm_yes", "parameters": {}}
                ]
            })
        
        if user_msg_lower in ['no', 'nei']:
            return json.dumps({
                "response": "No problem! Let me know if you need anything else.",
                "functions": [
                    {"name": "confirm_no", "parameters": {}}
                ]
            })
        
        # Check for "today's lesson" or "give me today's lesson" pattern
        if "today" in user_msg_lower and "lesson" in user_msg_lower:
            return json.dumps({
                "response": "Here is today's lesson for you.",
                "functions": [
                    {"name": "send_todays_lesson", "parameters": {}}
                ]
            })
        
        # For lesson status extraction
        # Check for "I am on lesson X" or "I'm on lesson X" pattern (more specific than just "lesson X")
        i_am_lesson_match = re.search(r'i\s*(?:am|\'m)\s+(?:on\s+)?lesson\s*(\d+)', user_msg, re.IGNORECASE)
        if i_am_lesson_match:
            lesson_num = i_am_lesson_match.group(1)
            response_text = f"Great! I'll note that you're currently on Lesson {lesson_num}."
            if next_question:
                response_text += f" {next_question}"
            return json.dumps({
                "response": response_text,
                "functions": [
                    {"name": "extract_memory", "parameters": {"key": MemoryKey.LESSON_CURRENT, "value": lesson_num, "confidence": 0.9}}
                ]
            })
        
        # Check for "lesson X" or "on lesson X" pattern
        lesson_match = re.search(r'(?:on\s+)?lesson\s*(\d+)', user_msg, re.IGNORECASE)
        if lesson_match:
            lesson_num = lesson_match.group(1)
            response_text = f"Great! I'll note that you're currently on Lesson {lesson_num}."
            if next_question:
                response_text += f" {next_question}"
            return json.dumps({
                "response": response_text,
                "functions": [
                    {"name": "extract_memory", "parameters": {"key": MemoryKey.LESSON_CURRENT, "value": lesson_num, "confidence": 0.9}}
                ]
            })
        
        # Check for just a number (e.g., "10")
        num_match = re.match(r'^(\d{1,3})$', user_msg)
        if num_match:
            lesson_num = num_match.group(1)
            response_text = f"Perfect! I'll set your current lesson to Lesson {lesson_num}."
            if next_question:
                response_text += f" {next_question}"
            return json.dumps({
                "response": response_text,
                "functions": [
                    {"name": "extract_memory", "parameters": {"key": MemoryKey.LESSON_CURRENT, "value": lesson_num, "confidence": 0.95}}
                ]
            })
        
        # Check for timezone/location mentions (e.g., "New York", "London", "Tokyo")
        # This handles cases where user provides a location instead of yes/no
        tz_match = re.search(r'\b(New\s+York|London|Tokyo|Paris|Berlin|Sydney|Los\s+Angeles|Chicago|Dubai|Mumbai|Singapore|Hong\s+Kong|Toronto|Vancouver|Oslo|Stockholm|Copenhagen|Helsinki|Madrid|Rome|Amsterdam|Zurich|Vienna|Brussels|Warsaw|Prague|Budapest|Athens|Istanbul|Cairo|Johannesburg|Nairobi|Lagos|Casablanca|Tel\s+Aviv|Dubai|Doha|Kuwait\s+City|Riyadh|Tehran|Karachi|Delhi|Mumbai|Kolkata|Chennai|Bangalore|Hyderabad|Pune|Ahmedabad|Dhaka|Kathmandu|Colombo|Male|Thimphu|Yangon|Bangkok|Phnom\s+Penh|Vientiane|Hanoi|Ho\s+Chi\s+Minh\s+City|Kuala\s+Lumpur|Singapore|Jakarta|Manila|Taipei|Seoul|Busan|Pyongyang|Beijing|Shanghai|Guangzhou|Shenzhen|Chengdu|Xi\'an|Wuhan|Nanjing|Hangzhou|Suzhou|Tianjin|Qingdao|Dalian|Shenyang|Changchun|Harbin|Kunming|Nanning|Guiyang|Lanzhou|Xining|Yinchuan|Urumqi|Lhasa|Hohhot|Taiyuan|Shijiazhuang|Jinan|Zhengzhou|Hefei|Nanchang|Fuzhou|Xiamen|Changsha|Wuhan|Ningbo|Wenzhou|Jinhua|Shaoxing|Jiaxing|Huzhou|Zhoushan|Taizhou|Quzhou|Lishui|Hainan|Sanya|Haikou|Danzhou|Wanning|Wenchang|Qionghai|Dongfang|Wuzhishan|Baoting|Baisha|Changjiang|Ledong|Lingao|Chengmai|Dingan|Tunchang|Qiongzhong|Baisha)\b', user_msg, re.IGNORECASE)
        if tz_match:
            location = tz_match.group(1)
            # Map common locations to timezones
            location_to_tz = {
                "new york": "America/New_York",
                "london": "Europe/London",
                "tokyo": "Asia/Tokyo",
                "paris": "Europe/Paris",
                "berlin": "Europe/Berlin",
                "sydney": "Australia/Sydney",
                "los angeles": "America/Los_Angeles",
                "chicago": "America/Chicago",
                "dubai": "Asia/Dubai",
                "mumbai": "Asia/Kolkata",
                "singapore": "Asia/Singapore",
                "hong kong": "Asia/Hong_Kong",
                "toronto": "America/Toronto",
                "vancouver": "America/Vancouver",
                "oslo": "Europe/Oslo",
                "stockholm": "Europe/Stockholm",
                "copenhagen": "Europe/Copenhagen",
                "helsinki": "Europe/Helsinki",
                "madrid": "Europe/Madrid",
                "rome": "Europe/Rome",
                "amsterdam": "Europe/Amsterdam",
                "zurich": "Europe/Zurich",
                "vienna": "Europe/Vienna",
                "brussels": "Europe/Brussels",
                "warsaw": "Europe/Warsaw",
                "prague": "Europe/Prague",
                "budapest": "Europe/Budapest",
                "athens": "Europe/Athens",
                "istanbul": "Europe/Istanbul",
            }
            tz = location_to_tz.get(location.lower(), "UTC")
            response_text = f"Great! You've shared your location as {location}. Is that correct? (yes/no)"
            if next_question:
                response_text += f" {next_question}"
            return json.dumps({
                "response": response_text,
                "functions": [
                    {"name": "set_timezone", "parameters": {"timezone": tz}}
                ]
            })
        
        # Check for "new" user
        if "new" in user_msg_lower:
            response_text = "Welcome! I'll start you with Lesson 1."
            if next_question:
                response_text += f" {next_question}"
            return json.dumps({
                "response": response_text,
                "functions": [
                    {"name": "extract_memory", "parameters": {"key": MemoryKey.LESSON_CURRENT, "value": "1", "confidence": 0.9}}
                ]
            })
        
        # Default response for other cases
        return json.dumps({
            "response": f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'}",
            "functions": []
        })
    
    mock_client.call_ollama = AsyncMock(side_effect=mock_call_ollama)
    
    # Patch the dialogue_engine module where DialogueEngine imports call_ollama
    # This must be done BEFORE any DialogueEngine instance is created
    import src.services.dialogue_engine as dialogue_engine_module
    monkeypatch.setattr(dialogue_engine_module, "call_ollama", mock_call_ollama)
    
    # Also patch the original location and the re-export location
    import src.services.dialogue as dialogue_module
    monkeypatch.setattr(dialogue_module, "call_ollama", mock_call_ollama)
    
    import src.services.dialogue.ollama_client as ollama_module
    monkeypatch.setattr(ollama_module, "call_ollama", mock_call_ollama)
    
    return mock_client


@pytest.fixture
def frozen_time() -> datetime.datetime:
    """Frozen datetime for deterministic time-based tests.
    
    Returns a fixed UTC datetime that can be used for consistent
    time-based assertions.
    """
    return datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
