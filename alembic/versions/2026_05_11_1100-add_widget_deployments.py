"""add widget deployments and chat memory

Revision ID: widget_deploy_20260511
Revises: widget_color_header_20260510
Create Date: 2026-05-11 11:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "widget_deploy_20260511"
down_revision: Union[str, None] = "widget_color_header_20260510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "widget_deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deployment_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("initial_messages", sa.JSON(), nullable=False),
        sa.Column("theme", sa.String(length=16), nullable=False),
        sa.Column("primary_color", sa.String(length=7), nullable=False),
        sa.Column("allowed_domains", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
        sa.UniqueConstraint("deployment_id"),
    )
    op.create_index(op.f("ix_widget_deployments_id"), "widget_deployments", ["id"], unique=False)
    op.create_index(op.f("ix_widget_deployments_agent_id"), "widget_deployments", ["agent_id"], unique=False)
    op.create_index(op.f("ix_widget_deployments_deployment_id"), "widget_deployments", ["deployment_id"], unique=True)

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deployment_id"], ["widget_deployments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_sessions_id"), "chat_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_chat_sessions_agent_id"), "chat_sessions", ["agent_id"], unique=False)
    op.create_index(op.f("ix_chat_sessions_deployment_id"), "chat_sessions", ["deployment_id"], unique=False)
    op.create_index(op.f("ix_chat_sessions_last_active_at"), "chat_sessions", ["last_active_at"], unique=False)
    op.create_index(op.f("ix_chat_sessions_visitor_hash"), "chat_sessions", ["visitor_hash"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_created_at"), "chat_messages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_created_at"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_chat_sessions_visitor_hash"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_last_active_at"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_deployment_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_agent_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index(op.f("ix_widget_deployments_deployment_id"), table_name="widget_deployments")
    op.drop_index(op.f("ix_widget_deployments_agent_id"), table_name="widget_deployments")
    op.drop_index(op.f("ix_widget_deployments_id"), table_name="widget_deployments")
    op.drop_table("widget_deployments")
