from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class AgentCreate(BaseModel):
    name: str
    instructions: Optional[str] = None


class AgentOut(BaseModel):
    id: UUID
    name: str
    instructions: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime

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


class AgentSettingsUpdate(BaseModel):
    """Schema for updating agent settings (instructions and widget configuration)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    instructions: Optional[str] = Field(None, max_length=5000)
    widget_theme: Optional[str] = Field(None, pattern="^(light|dark|auto)$")
    widget_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    widget_position: Optional[str] = Field(None, pattern="^(bottom-right|bottom-left|top-right|top-left)$")
    widget_greeting: Optional[str] = Field(None, max_length=200)


class WidgetConfig(BaseModel):
    """Widget configuration response"""
    theme: str
    color: str
    position: str
    greeting: str


class EmbedConfig(BaseModel):
    """Embed code configuration response"""
    script: str
    preview_url: str
    test_url: str
    npm_install: str


class AgentSettingsOut(BaseModel):
    """Complete agent settings response"""
    agent_id: str
    name: str
    instructions: str
    widget: WidgetConfig
    embed: EmbedConfig
    statistics: Dict[str, Any]
