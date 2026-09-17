"""add human_handoff_difficulty to agent_configs

Revision ID: handoff_difficulty_20260916
Revises: handoff_toggle_20260916
Create Date: 2026-09-16 13:00:00.000000

Adds:
  - agent_configs.human_handoff_difficulty varchar default 'balanced'
    Values: easy | balanced | hard  (easy = lenient, hard = strict)
    Controls how quickly the AI offers human handoff.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "handoff_difficulty_20260916"
down_revision: Union[str, None] = "handoff_toggle_20260916"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("human_handoff_difficulty", sa.String(length=16), server_default=sa.text("'balanced'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("agent_configs", "human_handoff_difficulty")
