from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from db import models, schemas
from api.auth.auth import get_db
from utils.jwt import get_current_user
from datetime import datetime, timedelta
import uuid

router = APIRouter()

@router.get("/credits", response_model=dict)
def get_credit_info(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """Get information about the user's credits and usage"""
    next_reset = user.last_reset_date + timedelta(days=30)
    
    max_credits = user.get_max_credits()
    
    agent_usage = db.query(
        models.Agent.id, 
        models.Agent.name,
        func.sum(models.UsageLog.credits_used).label("total_used")
    ).join(
        models.UsageLog, 
        models.UsageLog.agent_id == models.Agent.id
    ).filter(
        models.UsageLog.user_id == user.id,
        models.UsageLog.timestamp >= user.last_reset_date
    ).group_by(
        models.Agent.id, 
        models.Agent.name
    ).all()
    
    # Format the results
    agent_breakdown = [
        {
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "credits_used": agent.total_used or 0
        }
        for agent in agent_usage
    ]
    
    return {
        "user_type": user.user_type,
        "credits_remaining": user.credits_remaining,
        "max_credits": max_credits,
        "next_reset_date": next_reset,
        "days_until_reset": (next_reset - datetime.utcnow()).days,
        "agent_usage": agent_breakdown
    }

@router.post("/reset-credits")
def reset_credits(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """
    Manually reset a user's credits. In a production, this would be triggered
    by a scheduled job at the end of each billing cycle.
    """
    
    max_credits = user.get_max_credits()
    user.credits_remaining = max_credits
    user.last_reset_date = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return {
        "message": "Credits have been reset",
        "credits_remaining": user.credits_remaining,
        "next_reset": user.last_reset_date + timedelta(days=30)
    }

@router.get("/settings", response_model=schemas.UserSettingsOut)
def get_user_settings(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """Get user's settings. Creates default settings if none exist."""
    settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    
    if not settings:
        settings = models.UserSettings(user_id=user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings

@router.post("/settings", response_model=schemas.UserSettingsOut)
def create_user_settings(
    settings_data: schemas.UserSettingsCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Create or replace user settings."""
    existing_settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    
    if existing_settings:
        raise HTTPException(status_code=400, detail="User settings already exist. Use PUT to update.")
    
    # Create new settings
    settings = models.UserSettings(
        user_id=user.id,
        **settings_data.dict(exclude_unset=True)
    )
    
    db.add(settings)
    db.commit()
    db.refresh(settings)
    
    return settings

@router.put("/settings", response_model=schemas.UserSettingsOut)
def update_user_settings(
    settings_data: schemas.UserSettingsUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Update user settings. Creates default settings if none exist."""
    settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    
    if not settings:
        settings = models.UserSettings(user_id=user.id)
        db.add(settings)
        db.flush()
    
    update_data = settings_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)
    
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(settings)
    
    return settings

@router.delete("/settings")
def delete_user_settings(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """Delete user settings and revert to defaults."""
    settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="User settings not found")
    
    db.delete(settings)
    db.commit()
    
    return {"message": "User settings deleted successfully. Default settings will be used."}

@router.get("/settings/widget-config", response_model=dict)
def get_widget_config(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """Get widget configuration for the chat widget."""
    settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    
    if not settings:
        return {
            "theme": "default",
            "color": "#4a6cf7",
            "position": "bottom-right",
            "size": "medium",
            "language": "en",
            "auto_suggestions": True
        }
    
    return {
        "theme": settings.widget_theme,
        "color": settings.widget_color,
        "position": settings.widget_position,
        "size": settings.widget_size,
        "language": settings.default_language,
        "auto_suggestions": settings.auto_suggestions
    }