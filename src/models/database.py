import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(DB_DIR,'dev.db')}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Memory(Base):
    __tablename__ = "memory"
    memory_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    category = Column(String(50), nullable=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    value_hash = Column(String(128), nullable=True, index=True)
    confidence = Column(Integer, default=1)
    source = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    conflict_group_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    ttl_expires_at = Column(DateTime(timezone=True), nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


if __name__ == '__main__':
    init_db()
    print('Initialized DB at', DATABASE_URL)
