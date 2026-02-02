from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Load .env file if present
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./src/data/dev.db")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    SYSTEM_PROMPT: str = os.getenv("SYSTEM_PROMPT", "You are a spiritual coach specializing in A Course in Miracles. Respond with wisdom, compassion, and practical spiritual guidance.")
    # Add more config as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
