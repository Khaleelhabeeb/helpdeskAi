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
    """One row per text chunk with a 1024-dim Jina embedding (pgvector)."""

    __tablename__ = "kb_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # No FK: allows inserting a chunk before the parent commit; cascade delete is
    # handled in application code (delete_for_kb / delete_namespace)
    kb_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    namespace = Column(String, nullable=False, index=True)  # f"{user_id}:{agent_id}"
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(VectorType, nullable=False)  # type: ignore
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_kb_chunks_kb_chunk_idx", "kb_id", "chunk_index", unique=False),
        # HNSW index DDL lives in the migration: USING hnsw (embedding vector_cosine_ops)
    )
