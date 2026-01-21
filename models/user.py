from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from datetime import datetime
from db.database import Base
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
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)

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
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    credits_used = Column(Integer, default=1)
    message_content = Column(Text, nullable=True)
    response_content = Column(Text, nullable=True)

    user = relationship("User", backref="usage_logs")
    agent = relationship("Agent", backref="usage_logs")


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


class UserStorageUsage(Base):
    __tablename__ = "user_storage_usage"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    total_files = Column(Integer, default=0)
    total_size_bytes = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="storage_usage")
