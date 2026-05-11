import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.database import Base


def new_deployment_id() -> str:
    return uuid.uuid4().hex


class WidgetDeployment(Base):
    __tablename__ = "widget_deployments"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), unique=True, nullable=False, index=True)
    deployment_id = Column(String(64), unique=True, nullable=False, index=True, default=new_deployment_id)
    display_name = Column(String(120), nullable=False)
    logo_url = Column(Text, nullable=True)
    initial_messages = Column(JSON, nullable=False, default=list)
    theme = Column(String(16), default="dark", nullable=False)
    primary_color = Column(String(7), default="#ffffff", nullable=False)
    allowed_domains = Column(JSON, nullable=False, default=list)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="widget_deployment")
    sessions = relationship("ChatSession", back_populates="deployment", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    deployment_id = Column(Integer, ForeignKey("widget_deployments.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    visitor_hash = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    deployment = relationship("WidgetDeployment", back_populates="sessions")
    agent = relationship("Agent")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    session = relationship("ChatSession", back_populates="messages")
