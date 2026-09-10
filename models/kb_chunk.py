import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from db.database import Base
from pgvector.sqlalchemy import Vector  # type: ignore

_VECTOR_DIM = int(os.getenv("JINA_EMBEDDING_DIMENSION", "1024") or "1024")
VectorType = Vector(_VECTOR_DIM)  # type: ignore


class KbChunk(Base):
    """
    pgvector-backed chunk store — replaces Milvus collection.
    One row per text chunk with 1024-dim Jina embedding.

    Namespace is `f"{user_id}:{agent_id}"` for backward-compat filtering.
    HNSW index on embedding (cosine) created via migration for fast top-k.
    """

    __tablename__ = "kb_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Keep as plain UUID for flexibility (no FK) — allows insert before parent commit
    # and matches previous Milvus behavior where namespace/kb_id were just strings.
    # Cascade delete is handled via application: delete_for_kb / delete_namespace
    kb_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    namespace = Column(String, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(VectorType, nullable=False)  # type: ignore
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_kb_chunks_kb_chunk_idx", "kb_id", "chunk_index", unique=False),
        # HNSW index is created in migration via raw SQL for full control;
        # declare here for autogenerate awareness (no-op if exists)
        # Note: actual DDL for hnsw is in migration: USING hnsw (embedding vector_cosine_ops)
    )
