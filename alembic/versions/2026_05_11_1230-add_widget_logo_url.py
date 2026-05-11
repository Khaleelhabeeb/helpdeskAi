"""add widget logo url

Revision ID: widget_logo_20260511
Revises: widget_deploy_20260511
Create Date: 2026-05-11 12:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "widget_logo_20260511"
down_revision: Union[str, None] = "widget_deploy_20260511"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("widget_deployments", sa.Column("logo_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("widget_deployments", "logo_url")
