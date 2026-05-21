"""add kb source storage metadata

Revision ID: kb_source_storage_20260521
Revises: drop_s3_cols_20260521
Create Date: 2026-05-21 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "kb_source_storage_20260521"
down_revision: Union[str, None] = "drop_s3_cols_20260521"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("source_storage_url", sa.Text(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("source_storage_key", sa.String(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("source_content_type", sa.String(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("source_content_sha256", sa.String(length=64), nullable=True))
    op.create_index("ix_knowledge_bases_source_storage_key", "knowledge_bases", ["source_storage_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_bases_source_storage_key", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "source_content_sha256")
    op.drop_column("knowledge_bases", "source_content_type")
    op.drop_column("knowledge_bases", "source_storage_key")
    op.drop_column("knowledge_bases", "source_storage_url")
