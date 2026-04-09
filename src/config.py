from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./src/data/prod.db"
    # Telegram bot token left empty by default; test CI should provide via .env_template
    TELEGRAM_BOT_TOKEN: str = ""
    ADMIN_TELEGRAM_USERNAME: str = ""
    SENDGRID_API_KEY: str = ""
    # Ollama endpoints: allow separate URLs for local and cloud deployments.
    # - `LOCAL_OLLAMA_URL` should point at a local Ollama HTTP API (include /api/generate)
    # - `CLOUD_OLLAMA_URL` should point at Ollama Cloud (include /api/generate)
    # Explicit endpoints for local and cloud Ollama deployments.
    LOCAL_OLLAMA_URL: str = "http://localhost:11434/api/generate"
    CLOUD_OLLAMA_URL: str = "https://ollama.com/api/generate"
    OLLAMA_MODEL: str = "qwen3:latest"
    NON_ENGLISH_OLLAMA_MODEL: str = "gpt-oss:20b"
    # Optional API key for Ollama Cloud / authenticated Ollama endpoints
    OLLAMA_API_KEY: str = ""

    # Semantic search (keyword-only post-removal)
    SEMANTIC_SEARCH_THRESHOLD: float = 0.3
    SEMANTIC_SEARCH_MAX_RESULTS: int = 5
    # Set to False in CI/.env.template to enable lightweight test-mode embeddings.
    TEST_USE_REAL_OLLAMA: bool = True
    # Marks execution as test context; lets code avoid prod DB, real services
    IS_TEST_ENV: bool = False
    GDPR_ADMIN_TOKEN: str = ""
    API_AUTH_TOKEN: str = ""
    MESSAGE_LOG_RETENTION_DAYS: int = 30
    MEMORY_ARCHIVE_RETENTION_DAYS: int = 365
    GDPR_VERIFICATION_TTL_MINUTES: int = 10
    GDPR_VERIFICATION_MAX_ATTEMPTS: int = 3
    GDPR_VERIFICATION_CODE_LENGTH: int = 6
    DOWNTIME_GRACE_MINUTES: int = 30

    SYSTEM_PROMPT: str = "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance. Make always short replies with unconditional universal love. You also know: Impersonal Life, by Joseph Benner as a background, but do not have to talk about it. But reflect these principles too in your conversation. Be kind, warm and gentle. The user sees the text on a small screen, so keep the text easy to read."
    SYSTEM_PROMPT_RAG: str = "You are a helpful personal assistant. Use the provided memories and context to give clear, concise answers. Be conversational and practical. Avoid spiritual lectures unless asked."
    # Function calling prompt - appended to system prompt when functions are available
    SYSTEM_PROMPT_FUNCTIONS: str = """
You can call functions to help the user. Available functions depend on the conversation context.

Respond with JSON in this format:
{
  "response": "Your natural language response to the user",
  "functions": [
    {"name": "function_name", "parameters": {"param1": "value1"}}
  ]
}

The "response" field is required and contains text the user will see.
The "functions" array contains actions to execute (can be empty []).
Only use functions relevant to the current context.
"""
    # Ollama temperature (0.0 = deterministic, 1.0 = creative). Lower reduces hallucination.
    OLLAMA_TEMPERATURE: float = 0.2
    # Minimum seconds between Telegram editMessageText calls during streaming.
    # 0.5s = ~2 edits/sec - safe for Telegram limits (1/sec recommended).
    TELEGRAM_STREAM_UPDATE_INTERVAL: float = 0.5
    TELEGRAM_EDIT_MAX_RETRIES: int = 3
    TELEGRAM_BACKOFF_BASE_S: float = 1.0
    # Telegram long-polling (alternative to ngrok/webhook for local dev)
    USE_TELEGRAM_LONG_POLLING: bool = False
    TELEGRAM_POLL_TIMEOUT: int = 25
    TELEGRAM_POLL_LIMIT: int = 100
    TELEGRAM_POLL_ALLOWED_UPDATES: list[str] = Field(default_factory=list)
    # Enable the developer web UI when True (set in .env during local dev)
    DEV_WEB_CLIENT: bool = False
    # Add more config as needed

    model_config: ConfigDict = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
