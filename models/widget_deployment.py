import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


def new_deployment_id() -> str:
    return uuid.uuid4().hex


class WidgetDeployment(Base):
    __tablename__ = "widget_deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), unique=True, nullable=False, index=True)
    deployment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=new_deployment_id)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    initial_messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    theme: Mapped[str] = mapped_column(String(16), default="dark", nullable=False)
    primary_color: Mapped[str] = mapped_column(String(7), default="#ffffff", nullable=False)
    allowed_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="widget_deployment")
    sessions: Mapped[List["ChatSession"]] = relationship("ChatSession", back_populates="deployment", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("widget_deployments.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    visitor_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    
    # Identity fields for CRM integration
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    custom_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    deployment: Mapped["WidgetDeployment"] = relationship("WidgetDeployment", back_populates="sessions")
    agent: Mapped["Agent"] = relationship("Agent")
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
