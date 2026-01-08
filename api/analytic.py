from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from db import models
from api.auth.auth import get_db
from utils.jwt import get_current_user
from datetime import datetime, timedelta
from typing import List, Dict

router = APIRouter()

@router.get("/kpi/credits")
def get_credits_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return total credits used, credits remaining, and usage trend for the user."""
    total_credits_used = db.query(models.UsageLog).filter(models.UsageLog.user_id == user.id).count()
    credits_remaining = user.credits_remaining
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    usage_per_day = (
        db.query(models.UsageLog.timestamp)
        .filter(models.UsageLog.user_id == user.id, models.UsageLog.timestamp >= thirty_days_ago)
        .all()
    )
    # Aggregate by day
    trend = {}
    for log in usage_per_day:
        day = log.timestamp.date().isoformat()
        trend[day] = trend.get(day, 0) + 1
    return {
        "total_credits_used": total_credits_used,
        "credits_remaining": credits_remaining,
        "usage_trend": trend
    }

@router.get("/kpi/agent-interactions")
def get_agent_interactions_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return number of questions asked, responses received, and most active agent."""
    logs_with_agents = (
        db.query(models.UsageLog, models.Agent)
        .join(models.Agent, models.UsageLog.agent_id == models.Agent.id)
        .filter(models.UsageLog.user_id == user.id)
        .all()
    )
    
    agent_counts = {}
    for usage_log, agent in logs_with_agents:
        agent_name = agent.name if agent else "Unknown"
        agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1
    
    most_active_agent = max(agent_counts, key=agent_counts.get) if agent_counts else None
    return {
        "total_questions": len(logs_with_agents),
        "total_responses": len(logs_with_agents),
        "most_active_agent": most_active_agent,
        "agent_interaction_counts": agent_counts
    }

@router.get("/kpi/activity-timeline")
def get_activity_timeline_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return recent activity and peak usage times."""
    logs = (
        db.query(models.UsageLog)
        .options(joinedload(models.UsageLog.agent))
        .filter(models.UsageLog.user_id == user.id)
        .order_by(models.UsageLog.timestamp.desc())
        .limit(20)
        .all()
    )
    
    recent_activity = []
    hour_counts = {}
    
    for log in logs:
        agent_name = log.agent.name if log.agent else "Unknown"
        recent_activity.append({
            "timestamp": log.timestamp,
            "agent_name": agent_name,
            "question": log.message_content,
            "response": log.response_content
        })
        
        hour = log.timestamp.hour
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    peak_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None
    return {
        "recent_activity": recent_activity,
        "peak_usage_hour": peak_hour,
        "hourly_activity": hour_counts
    }

@router.get("/kpi/agent-performance")
def get_agent_performance_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return number of agents created and usage per agent."""
    agent_usage_query = (
        db.query(models.Agent.name, func.count(models.UsageLog.id).label('usage_count'))
        .outerjoin(models.UsageLog, 
                  (models.Agent.id == models.UsageLog.agent_id) & 
                  (models.UsageLog.user_id == user.id))
        .filter(models.Agent.user_id == user.id)
        .group_by(models.Agent.id, models.Agent.name)
        .all()
    )
    
    agent_stats = {}
    for agent_name, usage_count in agent_usage_query:
        agent_stats[agent_name] = usage_count
    
    return {
        "total_agents": len(agent_stats),
        "agent_usage": agent_stats
    }

@router.get("/kpi/engagement")
def get_engagement_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return days active and average questions per day."""
    logs = db.query(models.UsageLog).filter(models.UsageLog.user_id == user.id).all()
    days = set(log.timestamp.date() for log in logs)
    days_active = len(days)
    avg_questions_per_day = len(logs) / days_active if days_active else 0
    return {
        "days_active": days_active,
        "avg_questions_per_day": avg_questions_per_day
    }
