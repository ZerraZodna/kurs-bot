
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./src/data/prod.db"
    TELEGRAM_BOT_TOKEN: str = ""
    ADMIN_TELEGRAM_USERNAME: str = ""
    SLACK_BOT_TOKEN: str = ""
    SENDGRID_API_KEY: str = ""
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "qwen3:latest"
    OLLAMA_CHAT_RAG_MODEL: str = "llama3.2:3b"
    NON_ENGLISH_OLLAMA_MODEL: str = "gpt-oss:20b"
    # Optional API key for Ollama Cloud / authenticated Ollama endpoints
    OLLAMA_API_KEY: str = ""

    # Embedding settings for semantic search
    OLLAMA_EMBED_URL: str = "http://localhost:11434/api/embed"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text:latest"
    # Embedding backend: 'ollama' or 'local'
    EMBEDDING_BACKEND: str = "local"
    # Default dimension for the local recommended model (all-MiniLM-L6-v2)
    EMBEDDING_DIMENSION: int = 384
    SEMANTIC_SEARCH_THRESHOLD: float = 0.5
    SEMANTIC_SEARCH_MAX_RESULTS: int = 5
    # Trigger matcher defaults
    TRIGGER_SIMILARITY_THRESHOLD: float = 0.75
    TRIGGER_MATCHER_REFRESH_SECS: int = 300
    GDPR_ADMIN_TOKEN: str = ""
    API_AUTH_TOKEN: str = ""
    MESSAGE_LOG_RETENTION_DAYS: int = 30
    MEMORY_ARCHIVE_RETENTION_DAYS: int = 365
    GDPR_VERIFICATION_TTL_MINUTES: int = 10
    GDPR_VERIFICATION_MAX_ATTEMPTS: int = 3
    GDPR_VERIFICATION_CODE_LENGTH: int = 6
    DOWNTIME_GRACE_MINUTES: int = 10
    
    SYSTEM_PROMPT: str = "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance."
    SYSTEM_PROMPT_RAG: str = "You are a helpful personal assistant. Use the provided memories and context to give clear, concise answers. Be conversational and practical. Avoid lengthy spiritual lectures unless asked."
    # Add more config as needed

    model_config: ConfigDict = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

settings = Settings()
