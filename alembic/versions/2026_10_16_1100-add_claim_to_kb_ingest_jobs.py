"""multissafe ingest recovery: claim flag on kb_ingest_jobs

Revision ID: ingest_claim_20261016
Revises: drop_kb_source_storage_20261016

Hosts with autoscaling (e.g. FastAPI Cloud) can boot several replicas at
once, and each runs startup recovery. `claimed_by` lets exactly one replica
take ownership of each stuck job via an atomic UPDATE, so two replicas never
resume — or fail — the same job.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ingest_claim_20261016"
down_revision: Union[str, None] = "drop_kb_source_storage_20261016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("kb_ingest_jobs", sa.Column("claimed_by", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_ingest_jobs", "claimed_by")
