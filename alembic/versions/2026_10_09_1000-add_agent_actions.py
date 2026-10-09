"""add agent_actions (custom API actions)

Revision ID: agent_actions_20261009
Revises: help_page_20261008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "agent_actions_20261009"
down_revision: Union[str, None] = "help_page_20261008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("method", sa.String(8), nullable=False, server_default="GET"),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("headers_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", "name", name="uq_agent_actions_agent_name"),
    )
    op.create_index("ix_agent_actions_id", "agent_actions", ["id"])
    op.create_index("ix_agent_actions_agent_id", "agent_actions", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_actions_agent_id", table_name="agent_actions")
    op.drop_index("ix_agent_actions_id", table_name="agent_actions")
    op.drop_table("agent_actions")
