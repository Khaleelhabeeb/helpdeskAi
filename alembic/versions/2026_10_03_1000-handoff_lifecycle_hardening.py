"""handoff lifecycle hardening: timeouts, presence, audit clocks

Revision ID: handoff_lifecycle_20261003
Revises: handoff_difficulty_20260916

Adds to conversations:
  last_visitor_at, last_agent_at, queued_at, claimed_at, resolved_at,
  resolved_by, close_reason, requeue_count, queue_notified_count, transcript_sent_at
Adds human_presence table (DB-backed presence for multi-instance).
Backfills clocks from updated_at so existing rows get sane timeouts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "handoff_lifecycle_20261003"
down_revision: Union[str, None] = "handoff_difficulty_20260916"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("last_visitor_at", sa.DateTime(), nullable=True))
    op.add_column("conversations", sa.Column("last_agent_at", sa.DateTime(), nullable=True))
    op.add_column("conversations", sa.Column("queued_at", sa.DateTime(), nullable=True))
    op.add_column("conversations", sa.Column("claimed_at", sa.DateTime(), nullable=True))
    op.add_column("conversations", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("conversations", sa.Column("close_reason", sa.String(32), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("requeue_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "conversations",
        sa.Column("queue_notified_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("conversations", sa.Column("transcript_sent_at", sa.DateTime(), nullable=True))

    # Backfill: existing rows get updated_at as idle clock; queued/human get queued/claimed stamps
    op.execute(sa.text("UPDATE conversations SET last_visitor_at = updated_at WHERE last_visitor_at IS NULL"))
    op.execute(sa.text("UPDATE conversations SET last_agent_at = updated_at WHERE last_agent_at IS NULL"))
    op.execute(sa.text("UPDATE conversations SET queued_at = updated_at WHERE queued_at IS NULL AND status IN ('queued','human','resolved')"))
    op.execute(sa.text("UPDATE conversations SET claimed_at = updated_at WHERE claimed_at IS NULL AND status IN ('human','resolved')"))
    op.execute(sa.text("UPDATE conversations SET resolved_at = updated_at WHERE resolved_at IS NULL AND status = 'resolved'"))

    op.create_index("ix_conversations_status_updated", "conversations", ["status", "updated_at"])
    op.create_index("ix_conversations_status_queued", "conversations", ["status", "queued_at"])

    op.create_table(
        "human_presence",
        sa.Column(
            "human_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_heartbeat_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("connection_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("human_presence")
    op.drop_index("ix_conversations_status_queued", table_name="conversations")
    op.drop_index("ix_conversations_status_updated", table_name="conversations")
    for col in (
        "transcript_sent_at",
        "queue_notified_count",
        "requeue_count",
        "close_reason",
        "resolved_by",
        "resolved_at",
        "claimed_at",
        "queued_at",
        "last_agent_at",
        "last_visitor_at",
    ):
        op.drop_column("conversations", col)
