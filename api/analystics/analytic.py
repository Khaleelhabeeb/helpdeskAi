from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date, extract
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
    
    # Aggregate by day in the database
    usage_trend_query = (
        db.query(
            cast(models.UsageLog.timestamp, Date).label('day'),
            func.count(models.UsageLog.id).label('count')
        )
        .filter(models.UsageLog.user_id == user.id, models.UsageLog.timestamp >= thirty_days_ago)
        .group_by(cast(models.UsageLog.timestamp, Date))
        .order_by('day')
        .all()
    )
    
    trend = {day.isoformat(): count for day, count in usage_trend_query}
    
    return {
        "total_credits_used": total_credits_used,
        "credits_remaining": credits_remaining,
        "usage_trend": trend
    }

@router.get("/kpi/agent-interactions")
def get_agent_interactions_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return number of questions asked, responses received, and most active agent."""
    # Get counts per agent in one query
    agent_counts_query = (
        db.query(models.Agent.name, func.count(models.UsageLog.id).label('count'))
        .join(models.UsageLog, models.Agent.id == models.UsageLog.agent_id)
        .filter(models.UsageLog.user_id == user.id)
        .group_by(models.Agent.name)
        .all()
    )
    
    agent_counts = {name: count for name, count in agent_counts_query}
    total_questions = sum(agent_counts.values())
    most_active_agent = max(agent_counts, key=agent_counts.get) if agent_counts else None
    
    return {
        "total_questions": total_questions,
        "total_responses": total_questions,
        "most_active_agent": most_active_agent,
        "agent_interaction_counts": agent_counts
    }

@router.get("/kpi/activity-timeline")
def get_activity_timeline_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return recent activity and peak usage times."""
    # Recent activity is fine with limit
    logs = (
        db.query(models.UsageLog)
        .options(joinedload(models.UsageLog.agent))
        .filter(models.UsageLog.user_id == user.id)
        .order_by(models.UsageLog.timestamp.desc())
        .limit(20)
        .all()
    )
    
    recent_activity = [
        {
            "timestamp": log.timestamp,
            "agent_name": log.agent.name if log.agent else "Unknown",
            "question": log.message_content,
            "response": log.response_content
        }
        for log in logs
    ]
    
    # Calculate peak hour in the database across all history
    hour_counts_query = (
        db.query(
            extract('hour', models.UsageLog.timestamp).label('hour'),
            func.count(models.UsageLog.id).label('count')
        )
        .filter(models.UsageLog.user_id == user.id)
        .group_by(extract('hour', models.UsageLog.timestamp))
        .all()
    )
    
    hour_counts = {int(hour): count for hour, count in hour_counts_query}
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
    
    agent_stats = {name: count for name, count in agent_usage_query}
    
    return {
        "total_agents": len(agent_stats),
        "agent_usage": agent_stats
    }

@router.get("/kpi/engagement")
def get_engagement_kpi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return days active and average questions per day."""
    stats = (
        db.query(
            func.count(models.UsageLog.id).label('total_logs'),
            func.count(func.distinct(cast(models.UsageLog.timestamp, Date))).label('days_active')
        )
        .filter(models.UsageLog.user_id == user.id)
        .first()
    )
    
    total_logs = stats.total_logs if stats else 0
    days_active = stats.days_active if stats else 0
    avg_questions_per_day = total_logs / days_active if days_active > 0 else 0
    
    return {
        "days_active": days_active,
        "avg_questions_per_day": avg_questions_per_day
    }
