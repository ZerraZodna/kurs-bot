from sqlalchemy import Column, Integer, String, DateTime, Text
from src.models.base import Base
import datetime


class PromptTemplate(Base):
    __tablename__ = 'prompt_templates'

    id = Column(Integer, primary_key=True)
    key = Column(String(128), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    owner = Column(String(128), nullable=True)
    visibility = Column(String(32), default='public')  # public|private
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
