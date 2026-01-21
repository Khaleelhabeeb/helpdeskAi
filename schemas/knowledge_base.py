from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID
from .enums import KBSourceType, KBStatus, JobState


class KnowledgeBaseCreate(BaseModel):
    agent_id: UUID
    source_type: KBSourceType
    title: Optional[str] = None
    source_uri: Optional[str] = None 


class KnowledgeBaseOut(BaseModel):
    id: UUID
    agent_id: UUID
    source_type: KBSourceType
    source_uri: Optional[str]
    title: Optional[str]
    status: KBStatus
    tokens_estimate: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KBIngestJobOut(BaseModel):
    id: UUID
    kb_id: UUID
    state: JobState
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
