import uuid
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLAlchemyEnum, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID  # Use this if you're on PostgreSQL
from datetime import datetime, timedelta
from .database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_type = Column(String, default="free")
    credits_remaining = Column(Integer, default=100)
    last_reset_date = Column(DateTime, default=datetime.utcnow)

    def get_max_credits(self):
        if self.user_type == "free":
            return 100
        elif self.user_type == "paid":
            return 2000
        elif self.user_type == "pro":
            return 20000
        return 0
class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    credits_used = Column(Integer, default=1)
    message_content = Column(Text, nullable=True)
    response_content = Column(Text, nullable=True)

    user = relationship("User", backref="usage_logs")
    agent = relationship("Agent", backref="usage_logs")

class Agent(Base):
    __tablename__ = "agents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="agents")
    knowledge_bases = relationship("KnowledgeBase", back_populates="agent", cascade="all, delete-orphan")
    config = relationship("AgentConfig", back_populates="agent", uselist=False, cascade="all, delete-orphan")


class AgentConfig(Base):
    __tablename__ = "agent_configs"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), unique=True, nullable=False)
    retrieval_enabled = Column(Boolean, default=True)
    retrieval_top_k = Column(Integer, default=4)
    embedding_model = Column(String, nullable=True)
    vector_store_namespace = Column(String, nullable=True)
    system_prompt_locked = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="config")

class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    widget_theme = Column(String, default="default")
    widget_color = Column(String, default="#4a6cf7")
    widget_position = Column(String, default="bottom-right")
    widget_size = Column(String, default="medium") 
    
    email_notifications = Column(Boolean, default=True)
    browser_notifications = Column(Boolean, default=False)
    notification_frequency = Column(String, default="immediate")
    
    default_language = Column(String, default="en")
    response_style = Column(String, default="professional")
    max_response_length = Column(String, default="medium")  
    auto_suggestions = Column(Boolean, default=True)
    
    data_retention_days = Column(Integer, default=30)
    analytics_enabled = Column(Boolean, default=True)
    share_usage_data = Column(Boolean, default=False)
    
    api_rate_limit_preference = Column(String, default="standard")
    debug_mode = Column(Boolean, default=False)
    
    custom_preferences = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="settings")


class KBSourceType(enum.Enum):
    upload_pdf = "upload_pdf"
    upload_txt = "upload_txt"
    url = "url"
    text = "text"
    other = "other"


class KBStatus(enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class JobState(enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    source_type = Column(SQLAlchemyEnum(KBSourceType), nullable=False)
    source_uri = Column(Text, nullable=True)
    title = Column(String, nullable=True)
    status = Column(SQLAlchemyEnum(KBStatus), default=KBStatus.pending, nullable=False)
    tokens_estimate = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="knowledge_bases")
    jobs = relationship("KBIngestJob", back_populates="kb", cascade="all, delete-orphan")


class KBIngestJob(Base):
    __tablename__ = "kb_ingest_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    state = Column(SQLAlchemyEnum(JobState), default=JobState.queued, nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kb = relationship("KnowledgeBase", back_populates="jobs")
