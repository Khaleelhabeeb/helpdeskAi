"""add_identity_to_chat_sessions

Revision ID: identity_chat_20260614
Revises: kb_source_storage_20260521
Create Date: 2026-06-14 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'identity_chat_20260614'
down_revision = 'kb_source_storage_20260521'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add identity columns to chat_sessions
    op.add_column('chat_sessions', sa.Column('external_id', sa.String(255), nullable=True))
    op.add_column('chat_sessions', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('chat_sessions', sa.Column('name', sa.String(255), nullable=True))
    op.add_column('chat_sessions', sa.Column('custom_metadata', sa.JSON(), nullable=True, default=dict))
    
    # Create indexes for identity fields
    op.create_index('ix_chat_sessions_external_id', 'chat_sessions', ['external_id'])
    op.create_index('ix_chat_sessions_email', 'chat_sessions', ['email'])


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_email', 'chat_sessions')
    op.drop_index('ix_chat_sessions_external_id', 'chat_sessions')
    op.drop_column('chat_sessions', 'custom_metadata')
    op.drop_column('chat_sessions', 'name')
    op.drop_column('chat_sessions', 'email')
    op.drop_column('chat_sessions', 'external_id')
