"""add composite performance indexes

Revision ID: perf_indexes_20260518
Revises: widget_logo_20260511
Create Date: 2026-05-18 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "perf_indexes_20260518"
down_revision: Union[str, None] = "widget_logo_20260511"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_usage_logs_agent_id_timestamp_desc",
            "usage_logs",
            ["agent_id", sa.text("timestamp DESC")],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_usage_logs_user_id_timestamp_desc",
            "usage_logs",
            ["user_id", sa.text("timestamp DESC")],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_chat_messages_session_id_created_at_desc",
            "chat_messages",
            ["session_id", sa.text("created_at DESC")],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_kb_ingest_jobs_kb_id_created_at_desc",
            "kb_ingest_jobs",
            ["kb_id", sa.text("created_at DESC")],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_knowledge_bases_agent_id_created_at_desc",
            "knowledge_bases",
            ["agent_id", sa.text("created_at DESC")],
            unique=False,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_knowledge_bases_agent_id_created_at_desc",
            table_name="knowledge_bases",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_kb_ingest_jobs_kb_id_created_at_desc",
            table_name="kb_ingest_jobs",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_chat_messages_session_id_created_at_desc",
            table_name="chat_messages",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_usage_logs_user_id_timestamp_desc",
            table_name="usage_logs",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_usage_logs_agent_id_timestamp_desc",
            table_name="usage_logs",
            postgresql_concurrently=True,
        )
