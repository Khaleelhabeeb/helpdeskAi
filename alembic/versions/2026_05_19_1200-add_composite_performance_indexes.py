"""add composite performance indexes

Revision ID: composite_perf_20260519
Revises: widget_logo_20260511
Create Date: 2026-05-19 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "composite_perf_20260519"
down_revision: Union[str, None] = "widget_logo_20260511"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_usage_logs_agent_id_timestamp_desc",
        "usage_logs",
        ["agent_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_usage_logs_user_id_timestamp_desc",
        "usage_logs",
        ["user_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_chat_messages_session_id_created_at_desc",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_kb_ingest_jobs_kb_id_created_at_desc",
        "kb_ingest_jobs",
        ["kb_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_bases_agent_id_created_at_desc",
        "knowledge_bases",
        ["agent_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_bases_agent_id_created_at_desc", table_name="knowledge_bases")
    op.drop_index("ix_kb_ingest_jobs_kb_id_created_at_desc", table_name="kb_ingest_jobs")
    op.drop_index("ix_chat_messages_session_id_created_at_desc", table_name="chat_messages")
    op.drop_index("ix_usage_logs_user_id_timestamp_desc", table_name="usage_logs")
    op.drop_index("ix_usage_logs_agent_id_timestamp_desc", table_name="usage_logs")
