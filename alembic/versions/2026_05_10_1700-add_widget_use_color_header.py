"""add widget use color header

Revision ID: widget_color_header_20260510
Revises: add_kb_ingest_progress_20260509
Create Date: 2026-05-10 17:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "widget_color_header_20260510"
down_revision: Union[str, None] = "add_kb_ingest_progress_20260509"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("widget_use_color_header", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("agent_configs", "widget_use_color_header", server_default=None)


def downgrade() -> None:
    op.drop_column("agent_configs", "widget_use_color_header")
