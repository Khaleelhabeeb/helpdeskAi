import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from db.database import Base
from sqlalchemy.orm import relationship
from .enums import KBSourceType, KBStatus, JobState


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    source_type = Column(SQLAlchemyEnum(KBSourceType), nullable=False)
    source_uri = Column(Text, nullable=True)
    title = Column(String, nullable=True)
    status = Column(SQLAlchemyEnum(KBStatus), default=KBStatus.pending, nullable=False, index=True)
    original_filename = Column(String, nullable=True)
    source_storage_url = Column(Text, nullable=True)
    source_storage_key = Column(String, nullable=True)
    source_content_type = Column(String, nullable=True)
    source_content_sha256 = Column(String(64), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    extracted_size_bytes = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    embedding_cost = Column(Integer, nullable=True)
    
    tokens_estimate = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="knowledge_bases")
    jobs = relationship("KBIngestJob", back_populates="kb", cascade="all, delete-orphan")

    @property
    def has_stored_source(self) -> bool:
        return bool(self.source_storage_key or self.source_storage_url)


class KBIngestJob(Base):
    __tablename__ = "kb_ingest_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    state = Column(SQLAlchemyEnum(JobState), default=JobState.queued, nullable=False, index=True)
    total_chunks = Column(Integer, nullable=True)
    processed_chunks = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kb = relationship("KnowledgeBase", back_populates="jobs")
