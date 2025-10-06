from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum


class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    user_type: str

    class Config:
        from_attributes = True

class AgentCreate(BaseModel):
    name: str
    instructions: Optional[str] = None

class AgentOut(BaseModel):
    id: UUID  # Update only this
    name: str
    instructions: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class UsageLogCreate(BaseModel):
    agent_id: UUID
    credits_used: int = 1
    message_content: Optional[str] = None
    response_content: Optional[str] = None

class UsageLogOut(BaseModel):
    id: int
    agent_id: UUID
    timestamp: datetime
    credits_used: int
    message_content: Optional[str]
    response_content: Optional[str]

    class Config:
        from_attributes = True


class AgentConfigOut(BaseModel):
    agent_id: UUID
    retrieval_enabled: bool
    retrieval_top_k: int
    embedding_model: Optional[str]
    vector_store_namespace: Optional[str]
    system_prompt_locked: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- RAG Schemas ---

class KBSourceType(str, Enum):
    upload_pdf = "upload_pdf"
    upload_txt = "upload_txt"
    url = "url"
    text = "text"
    other = "other"


class KBStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


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

class UserWithCredits(BaseModel):
    id: int
    email: EmailStr
    user_type: str
    credits_remaining: int
    last_reset_date: datetime

    class Config:
        from_attributes = True

class UserSettingsCreate(BaseModel):
    widget_theme: Optional[str] = Field(default="default", description="Widget theme: default, dark, light")
    widget_color: Optional[str] = Field(default="#4a6cf7", description="Primary color for widget")
    widget_position: Optional[str] = Field(default="bottom-right", description="Widget position: bottom-right, bottom-left, top-right, top-left")
    widget_size: Optional[str] = Field(default="medium", description="Widget size: small, medium, large")
    
    email_notifications: Optional[bool] = Field(default=True, description="Enable email notifications")
    browser_notifications: Optional[bool] = Field(default=False, description="Enable browser notifications")
    notification_frequency: Optional[str] = Field(default="immediate", description="Notification frequency: immediate, daily, weekly")
    
    default_language: Optional[str] = Field(default="en", description="Default language code")
    response_style: Optional[str] = Field(default="professional", description="Response style: professional, casual, friendly")
    max_response_length: Optional[str] = Field(default="medium", description="Max response length: short, medium, long")
    auto_suggestions: Optional[bool] = Field(default=True, description="Enable auto-suggestions")
    
    data_retention_days: Optional[int] = Field(default=30, ge=1, le=365, description="Data retention period in days")
    analytics_enabled: Optional[bool] = Field(default=True, description="Enable analytics")
    share_usage_data: Optional[bool] = Field(default=False, description="Share usage data for improvements")
    
    api_rate_limit_preference: Optional[str] = Field(default="standard", description="API rate limit preference: conservative, standard, aggressive")
    debug_mode: Optional[bool] = Field(default=False, description="Enable debug mode")
    
    custom_preferences: Optional[Dict[str, Any]] = Field(default=None, description="Custom user preferences as JSON")

class UserSettingsUpdate(BaseModel):
    widget_theme: Optional[str] = Field(None, description="Widget theme: default, dark, light")
    widget_color: Optional[str] = Field(None, description="Primary color for widget")
    widget_position: Optional[str] = Field(None, description="Widget position: bottom-right, bottom-left, top-right, top-left")
    widget_size: Optional[str] = Field(None, description="Widget size: small, medium, large")
    
    email_notifications: Optional[bool] = Field(None, description="Enable email notifications")
    browser_notifications: Optional[bool] = Field(None, description="Enable browser notifications")
    notification_frequency: Optional[str] = Field(None, description="Notification frequency: immediate, daily, weekly")
    
    default_language: Optional[str] = Field(None, description="Default language code")
    response_style: Optional[str] = Field(None, description="Response style: professional, casual, friendly")
    max_response_length: Optional[str] = Field(None, description="Max response length: short, medium, long")
    auto_suggestions: Optional[bool] = Field(None, description="Enable auto-suggestions")
    
    data_retention_days: Optional[int] = Field(None, ge=1, le=365, description="Data retention period in days")
    analytics_enabled: Optional[bool] = Field(None, description="Enable analytics")
    share_usage_data: Optional[bool] = Field(None, description="Share usage data for improvements")
    
    api_rate_limit_preference: Optional[str] = Field(None, description="API rate limit preference: conservative, standard, aggressive")
    debug_mode: Optional[bool] = Field(None, description="Enable debug mode")
    
    custom_preferences: Optional[Dict[str, Any]] = Field(None, description="Custom user preferences as JSON")

class UserSettingsOut(BaseModel):
    id: int
    user_id: int
    
    widget_theme: str
    widget_color: str
    widget_position: str
    widget_size: str
    
    email_notifications: bool
    browser_notifications: bool
    notification_frequency: str
    
    default_language: str
    response_style: str
    max_response_length: str
    auto_suggestions: bool
    
    data_retention_days: int
    analytics_enabled: bool
    share_usage_data: bool
    
    api_rate_limit_preference: str
    debug_mode: bool
    
    custom_preferences: Optional[Dict[str, Any]]
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
