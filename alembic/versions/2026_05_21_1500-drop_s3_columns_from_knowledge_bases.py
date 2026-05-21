"""drop s3 columns from knowledge_bases

Revision ID: drop_s3_cols_20260521
Revises: composite_perf_20260519
Create Date: 2026-05-21 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "drop_s3_cols_20260521"
down_revision: Union[str, None] = "composite_perf_20260519"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("knowledge_bases", "s3_region")
    op.drop_column("knowledge_bases", "s3_extracted_key")
    op.drop_column("knowledge_bases", "s3_original_key")


def downgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("s3_original_key", sa.String(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("s3_extracted_key", sa.String(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("s3_region", sa.String(), nullable=True))
