"""Human-handoff models: human agents, their AI-agent assignments, and conversation
threads. `ChatMessage` gains `sender_type`/`sender_id` columns via migration; the ORM
model itself lives in models/widget_deployment.py.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class HumanAgent(Base):
    __tablename__ = "human_agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # invited | active | disabled
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="invited")
    invite_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    invite_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_user_id", "email", name="uq_human_agents_owner_email"),
    )

    assignments: Mapped[List["AgentAssignment"]] = relationship(
        "AgentAssignment", back_populates="human_agent", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        foreign_keys="Conversation.assigned_human_agent_id",
        back_populates="assigned_human_agent",
    )


class AgentAssignment(Base):
    __tablename__ = "agent_assignments"

    human_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    human_agent: Mapped["HumanAgent"] = relationship("HumanAgent", back_populates="assignments")
    agent: Mapped["Agent"] = relationship("Agent")  # type: ignore[name-defined]


class Conversation(Base):
    """A chat thread and its handoff state machine: bot → collecting_email → queued → human → resolved."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("widget_deployments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Null until the first bot message
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    visitor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    visitor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # bot | collecting_email | queued | human | resolved
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="bot", index=True)

    assigned_human_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
    # Last time a fallback "we'll follow up" email was sent
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Lifecycle hardening: idle/timeout clocks (nullable for backfill compat)
    last_visitor_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_agent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("human_agents.id", ondelete="SET NULL"), nullable=True
    )
    # visitor_idle | agent_idle | queue_timeout | email_timeout | manual
    close_reason: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    requeue_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    queue_notified_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    transcript_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_conversations_agent_status", "agent_id", "status"),
        Index("ix_conversations_visitor", "visitor_id"),
        Index("ix_conversations_status_updated", "status", "updated_at"),
        Index("ix_conversations_status_queued", "status", "queued_at"),
    )

    assigned_human_agent: Mapped[Optional["HumanAgent"]] = relationship(
        "HumanAgent",
        foreign_keys=[assigned_human_agent_id],
        back_populates="conversations",
    )
    agent: Mapped["Agent"] = relationship("Agent")  # type: ignore[name-defined]


class HumanPresence(Base):
    """DB-backed presence so N replicas agree on who is online.

    Written on WS connect/heartbeat/disconnect (debounced); sweeper and
    fallback-email gates read this instead of in-memory counters.
    """

    __tablename__ = "human_presence"

    human_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    connection_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
