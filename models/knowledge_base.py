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
    
    # S3 Storage fields
    s3_original_key = Column(String, nullable=True)
    s3_extracted_key = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    extracted_size_bytes = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    embedding_cost = Column(Integer, nullable=True)
    s3_region = Column(String, default="us-east-1")
    
    tokens_estimate = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="knowledge_bases")
    jobs = relationship("KBIngestJob", back_populates="kb", cascade="all, delete-orphan")


class KBIngestJob(Base):
    __tablename__ = "kb_ingest_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    state = Column(SQLAlchemyEnum(JobState), default=JobState.queued, nullable=False, index=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kb = relationship("KnowledgeBase", back_populates="jobs")
