
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./src/data/prod.db"
    TELEGRAM_BOT_TOKEN: str = ""
    ADMIN_TELEGRAM_USERNAME: str = ""
    SLACK_BOT_TOKEN: str = ""
    SENDGRID_API_KEY: str = ""
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "qwen3:latest"
    MEMORY_EXTRACTOR_MODEL: str = "qwen3:latest"
    OLLAMA_CHAT_RAG_MODEL: str = "llama3.2:3b"
    MEMORY_EXTRACTOR_RAG_MODEL: str = "llama3.2:3b"
    
    # Embedding settings for semantic search
    OLLAMA_EMBED_URL: str = "http://localhost:11434/api/embed"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text:latest"
    EMBEDDING_DIMENSION: int = 768
    SEMANTIC_SEARCH_THRESHOLD: float = 0.4
    SEMANTIC_SEARCH_MAX_RESULTS: int = 5
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
