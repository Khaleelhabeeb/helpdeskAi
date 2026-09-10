"""migrate to pgvector (replace milvus)

Revision ID: pgvector_20250911
Revises: identity_chat_20260614
Create Date: 2026-09-11 12:00:00.000000

Replaces Milvus/Zilliz with Supabase pgvector (vector 0.8.0).
- Enables `vector` and `pgcrypto` (for gen_random_uuid)
- Creates `kb_chunks` table with 1024-dim Jina embeddings
- HNSW cosine index for fast top-k retrieval
- B-tree indexes for namespace / kb / agent filtering
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "pgvector_20250911"
down_revision: Union[str, None] = "identity_chat_20260614"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VECTOR_DIM = 1024  # must match JINA_EMBEDDING_DIMENSION / services/vector_store
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 64


def upgrade() -> None:
    # Extensions — Supabase already has vector 0.8.0, but idempotent
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Table — IF NOT EXISTS for idempotency on re-run
    # No FK to knowledge_bases/agents for flexibility (matches Milvus loose coupling);
    # deletes are handled via explicit `delete_for_kb` / `delete_namespace`.
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kb_id UUID NOT NULL,
            agent_id UUID NOT NULL,
            namespace TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding vector({VECTOR_DIM}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # B-tree indexes for filtered search
    op.execute("CREATE INDEX IF NOT EXISTS ix_kb_chunks_namespace ON kb_chunks (namespace);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_kb_chunks_kb_id ON kb_chunks (kb_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_kb_chunks_agent_id ON kb_chunks (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_kb_chunks_created_at ON kb_chunks (created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_kb_chunks_kb_chunk_idx ON kb_chunks (kb_id, chunk_index);")

    # HNSW cosine index — pgvector 0.8+ supports fast filtered search
    # If table is empty, creation is instant; for large tables CONCURRENTLY would be needed.
    op.execute(
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE tablename = 'kb_chunks' AND indexname = 'ix_kb_chunks_embedding_hnsw'
            ) THEN
                CREATE INDEX ix_kb_chunks_embedding_hnsw
                ON kb_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = {HNSW_M}, ef_construction = {HNSW_EF_CONSTRUCTION});
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_kb_chunk_idx;")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_agent_id;")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_kb_id;")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_namespace;")
    op.execute("DROP TABLE IF EXISTS kb_chunks;")
    # Keep extension (shared)
