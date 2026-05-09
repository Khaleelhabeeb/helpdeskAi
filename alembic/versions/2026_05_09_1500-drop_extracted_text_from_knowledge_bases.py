"""drop extracted_text from knowledge_bases

Revision ID: drop_extracted_text_20260509
Revises: add_extracted_text_20260509
Create Date: 2026-05-09 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "drop_extracted_text_20260509"
down_revision: Union[str, None] = "add_extracted_text_20260509"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("knowledge_bases", "extracted_text")


def downgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("extracted_text", sa.Text(), nullable=True))
