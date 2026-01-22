import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from db.database import Base
from sqlalchemy.orm import relationship


class Agent(Base):
    __tablename__ = "agents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String, nullable=False)
    instructions = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)  # S3 key for agent avatar image
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="agents")
    knowledge_bases = relationship("KnowledgeBase", back_populates="agent", cascade="all, delete-orphan")
    config = relationship("AgentConfig", back_populates="agent", uselist=False, cascade="all, delete-orphan")


class AgentConfig(Base):
    __tablename__ = "agent_configs"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), unique=True, nullable=False, index=True)
    retrieval_enabled = Column(Boolean, default=True)
    retrieval_top_k = Column(Integer, default=4)
    embedding_model = Column(String, nullable=True)
    vector_store_namespace = Column(String, nullable=True)
    system_prompt_locked = Column(Boolean, default=True)
    
    # Widget/Embed Configuration
    widget_theme = Column(String, default="light")
    widget_color = Column(String, default="#4a6cf7")
    widget_position = Column(String, default="bottom-right")
    widget_greeting = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="config")
