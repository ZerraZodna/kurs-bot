from sqlalchemy import Column, Integer, String, DateTime, Float, LargeBinary
from src.models.base import Base
import datetime


class TriggerEmbedding(Base):
    __tablename__ = 'trigger_embeddings'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    action_type = Column(String(64), nullable=False)
    embedding = Column(LargeBinary, nullable=False)
    threshold = Column(Float, default=0.75, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
