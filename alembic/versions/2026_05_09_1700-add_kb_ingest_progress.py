"""add kb ingest progress fields

Revision ID: add_kb_ingest_progress_20260509
Revises: drop_extracted_text_20260509
Create Date: 2026-05-09 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_kb_ingest_progress_20260509"
down_revision: Union[str, None] = "drop_extracted_text_20260509"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kb_ingest_jobs", sa.Column("total_chunks", sa.Integer(), nullable=True))
    op.add_column("kb_ingest_jobs", sa.Column("processed_chunks", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_ingest_jobs", "processed_chunks")
    op.drop_column("kb_ingest_jobs", "total_chunks")
