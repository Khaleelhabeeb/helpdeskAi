"""answer quality: chat_messages.answer_status + answer_corrections

Revision ID: answer_quality_20261009
Revises: agent_actions_20261009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "answer_quality_20261009"
down_revision: Union[str, None] = "agent_actions_20261009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no default: instant on Postgres even for a large table; old rows stay unclassified
    op.add_column("chat_messages", sa.Column("answer_status", sa.String(16), nullable=True))
    op.create_index("ix_chat_messages_answer_status", "chat_messages", ["answer_status"])

    op.create_table(
        "answer_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_key", sa.String(200), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_answer_corrections_id", "answer_corrections", ["id"])
    op.create_index("ix_answer_corrections_agent_id", "answer_corrections", ["agent_id"])
    op.create_index("ix_answer_corrections_kb_id", "answer_corrections", ["kb_id"])
    op.create_index("ix_answer_corrections_question_key", "answer_corrections", ["question_key"])


def downgrade() -> None:
    op.drop_index("ix_answer_corrections_question_key", table_name="answer_corrections")
    op.drop_index("ix_answer_corrections_kb_id", table_name="answer_corrections")
    op.drop_index("ix_answer_corrections_agent_id", table_name="answer_corrections")
    op.drop_index("ix_answer_corrections_id", table_name="answer_corrections")
    op.drop_table("answer_corrections")
    op.drop_index("ix_chat_messages_answer_status", table_name="chat_messages")
    op.drop_column("chat_messages", "answer_status")
