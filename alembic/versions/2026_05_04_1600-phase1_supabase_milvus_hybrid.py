"""phase1 supabase auth milvus hybrid search

Revision ID: phase1_supabase_milvus_hybrid
Revises: 687b431d57a9
Create Date: 2026-05-04 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "phase1_supabase_milvus_hybrid"
down_revision: Union[str, None] = "687b431d57a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("supabase_user_id", sa.String(), nullable=True))
    op.create_index("ix_users_supabase_user_id", "users", ["supabase_user_id"], unique=True)

    op.add_column(
        "agents",
        sa.Column(
            "model",
            sa.String(),
            nullable=False,
            server_default="groq/openai/gpt-oss-20b",
        ),
    )
    op.alter_column("agents", "model", server_default=None)



def downgrade() -> None:
    op.drop_column("agents", "model")
    op.drop_index("ix_users_supabase_user_id", table_name="users")
    op.drop_column("users", "supabase_user_id")
