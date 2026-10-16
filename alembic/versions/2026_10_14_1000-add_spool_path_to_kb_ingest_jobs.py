"""ingest spool durability: track transient spool path on kb_ingest_jobs

Revision ID: ingest_spool_20261014
Revises: answer_quality_20261009

Customer originals are no longer stored remotely — indexing runs from a
short-lived local spool file. Persisting its path on the job row lets startup
recovery re-enqueue jobs interrupted by a crash instead of losing them.
Spool files are deleted on success, on KB delete, or by the orphan sweeper.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ingest_spool_20261014"
down_revision: Union[str, None] = "answer_quality_20261009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no default: instant on Postgres; old rows simply have no spool.
    op.add_column("kb_ingest_jobs", sa.Column("transient_spool_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("kb_ingest_jobs", "transient_spool_path")
