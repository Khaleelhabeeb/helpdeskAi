"""add extracted_text to knowledge_bases

Revision ID: add_extracted_text_20260509
Revises: phase1_supabase_milvus_hybrid
Create Date: 2026-05-09 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_extracted_text_20260509"
down_revision: Union[str, None] = "phase1_supabase_milvus_hybrid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_bases", "extracted_text")
