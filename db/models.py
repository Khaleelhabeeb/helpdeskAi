# Backward compatibility - imports from new modular structure
from models import (
    User,
    UsageLog,
    UserSettings,
    UserStorageUsage,
    Agent,
    AgentConfig,
    KnowledgeBase,
    KBIngestJob,
    KBSourceType,
    KBStatus,
    JobState,
)

__all__ = [
    "User",
    "UsageLog",
    "UserSettings",
    "UserStorageUsage",
    "Agent",
    "AgentConfig",
    "KnowledgeBase",
    "KBIngestJob",
    "KBSourceType",
    "KBStatus",
    "JobState",
]
