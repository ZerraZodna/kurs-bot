
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./src/data/prod.db"
    TELEGRAM_BOT_TOKEN: str = ""
    SLACK_BOT_TOKEN: str = ""
    SENDGRID_API_KEY: str = ""
    OLLAMA_MODEL: str = "llama3.1:8b"
    SYSTEM_PROMPT: str = "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance."
    # Add more config as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
