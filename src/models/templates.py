from sqlalchemy import Column, DateTime, Integer, String, Text

from src.core.timezone import utc_now
from src.models.base import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True)
    key = Column(String(128), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    owner = Column(String(128), nullable=True)
    visibility = Column(String(32), default="public")  # public|private
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
