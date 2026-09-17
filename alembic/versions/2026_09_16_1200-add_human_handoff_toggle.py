"""add human_handoff_enabled toggle to agent_configs

Revision ID: handoff_toggle_20260916
Revises: handoff_20260914
Create Date: 2026-09-16 12:00:00.000000

Adds:
  - agent_configs.human_handoff_enabled boolean default false
  The feature is OFF by default if owner has no team; owner can enable only
  if at least one active human agent is assigned to the agent (enforced in API).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "handoff_toggle_20260916"
down_revision: Union[str, None] = "handoff_20260914"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("human_handoff_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("agent_configs", "human_handoff_enabled")
