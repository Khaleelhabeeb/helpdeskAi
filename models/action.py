import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class AgentAction(Base):
    """A custom API call the agent can make mid-conversation (exposed to the LLM as a tool)."""

    __tablename__ = "agent_actions"
    __table_args__ = (UniqueConstraint("agent_id", "name", name="uq_agent_actions_agent_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Tool name the LLM sees: snake_case, unique per agent
    name: Mapped[str] = mapped_column(String(48), nullable=False)
    # Tells the LLM when to use it — the most important field for quality
    description: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False, default="GET")
    # May contain {param} placeholders filled from the LLM's arguments
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # [{name, type: string|number|boolean, description, required}]
    parameters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Fernet-encrypted JSON object of header name -> value (may hold API keys)
    headers_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
