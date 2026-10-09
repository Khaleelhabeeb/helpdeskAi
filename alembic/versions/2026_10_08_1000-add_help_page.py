"""add help page settings to widget_deployments

Revision ID: help_page_20261008
Revises: handoff_lifecycle_20261003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "help_page_20261008"
down_revision: Union[str, None] = "handoff_lifecycle_20261003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("widget_deployments", sa.Column("help_page_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("widget_deployments", sa.Column("help_page_slug", sa.String(48), nullable=True))
    op.add_column("widget_deployments", sa.Column("help_page_title", sa.String(120), nullable=True))
    op.add_column("widget_deployments", sa.Column("help_page_description", sa.String(300), nullable=True))
    op.add_column("widget_deployments", sa.Column("help_page_suggestions", sa.JSON(), nullable=False, server_default="[]"))
    op.create_index("ix_widget_deployments_help_page_slug", "widget_deployments", ["help_page_slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_widget_deployments_help_page_slug", table_name="widget_deployments")
    op.drop_column("widget_deployments", "help_page_suggestions")
    op.drop_column("widget_deployments", "help_page_description")
    op.drop_column("widget_deployments", "help_page_title")
    op.drop_column("widget_deployments", "help_page_slug")
    op.drop_column("widget_deployments", "help_page_enabled")
