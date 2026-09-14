"""add human handoff tables

Revision ID: handoff_20260914
Revises: pgvector_20250911
Create Date: 2026-09-14 10:00:00.000000

Adds:
  - human_agents
  - agent_assignments
  - conversations
  - chat_messages.sender_type  (default 'visitor')
  - chat_messages.sender_id    (nullable uuid)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "handoff_20260914"
down_revision: Union[str, None] = "pgvector_20250911"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── human_agents ──────────────────────────────────────────────────────────
    op.create_table(
        "human_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="invited"),
        sa.Column("invite_token", sa.String(128), nullable=True),
        sa.Column("invite_token_expires", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("owner_user_id", "email", name="uq_human_agents_owner_email"),
    )
    op.create_index("ix_human_agents_id", "human_agents", ["id"])
    op.create_index("ix_human_agents_owner_user_id", "human_agents", ["owner_user_id"])
    op.create_index("ix_human_agents_invite_token", "human_agents", ["invite_token"])

    # ── agent_assignments ─────────────────────────────────────────────────────
    op.create_table(
        "agent_assignments",
        sa.Column(
            "human_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # ── conversations ─────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("widget_deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visitor_id", sa.String(128), nullable=False),
        sa.Column("visitor_email", sa.String(255), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="bot"),
        sa.Column(
            "assigned_human_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_conversations_id", "conversations", ["id"])
    op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])
    op.create_index("ix_conversations_deployment_id", "conversations", ["deployment_id"])
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])
    op.create_index("ix_conversations_visitor_id", "conversations", ["visitor_id"])
    op.create_index("ix_conversations_assigned_human_agent_id", "conversations", ["assigned_human_agent_id"])
    op.create_index("ix_conversations_agent_status", "conversations", ["agent_id", "status"])

    # ── chat_messages: new columns ────────────────────────────────────────────
    op.add_column(
        "chat_messages",
        sa.Column("sender_type", sa.String(16), nullable=False, server_default="visitor"),
    )
    op.add_column(
        "chat_messages",
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "sender_id")
    op.drop_column("chat_messages", "sender_type")

    op.drop_index("ix_conversations_agent_status", table_name="conversations")
    op.drop_index("ix_conversations_assigned_human_agent_id", table_name="conversations")
    op.drop_index("ix_conversations_visitor_id", table_name="conversations")
    op.drop_index("ix_conversations_session_id", table_name="conversations")
    op.drop_index("ix_conversations_deployment_id", table_name="conversations")
    op.drop_index("ix_conversations_agent_id", table_name="conversations")
    op.drop_index("ix_conversations_id", table_name="conversations")
    op.drop_table("conversations")

    op.drop_table("agent_assignments")

    op.drop_index("ix_human_agents_invite_token", table_name="human_agents")
    op.drop_index("ix_human_agents_owner_user_id", table_name="human_agents")
    op.drop_index("ix_human_agents_id", table_name="human_agents")
    op.drop_table("human_agents")
