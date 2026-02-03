
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./src/data/prod.db"
    TELEGRAM_BOT_TOKEN: str = ""
    SLACK_BOT_TOKEN: str = ""
    SENDGRID_API_KEY: str = ""
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "qwen3:latest"
    MEMORY_EXTRACTOR_MODEL: str = "qwen3:latest"
    
    # Embedding settings for semantic search
    OLLAMA_EMBED_URL: str = "http://localhost:11434/api/embed"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text:latest"
    EMBEDDING_DIMENSION: int = 768
    SEMANTIC_SEARCH_THRESHOLD: float = 0.4
    SEMANTIC_SEARCH_MAX_RESULTS: int = 5
    
    SYSTEM_PROMPT: str = "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance."
    # Add more config as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
