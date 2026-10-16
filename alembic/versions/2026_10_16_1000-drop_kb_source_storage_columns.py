"""drop legacy remote-source columns from knowledge_bases

Revision ID: drop_kb_source_storage_20261016
Revises: ingest_spool_20261014

Customer originals are no longer uploaded anywhere, so the worker URL/key
columns are dead. Run scripts/purge_legacy_kb_storage.py --apply BEFORE this
migration so no orphaned R2 objects are left behind. `source_content_type`
and `source_content_sha256` stay: they now describe the indexed text.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "drop_kb_source_storage_20261016"
down_revision: Union[str, None] = "ingest_spool_20261014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_knowledge_bases_source_storage_key", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "source_storage_key")
    op.drop_column("knowledge_bases", "source_storage_url")


def downgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("source_storage_url", sa.Text(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("source_storage_key", sa.String(), nullable=True))
    op.create_index("ix_knowledge_bases_source_storage_key", "knowledge_bases", ["source_storage_key"], unique=False)
