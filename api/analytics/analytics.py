from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date, extract
from db import models
from api.auth.auth import get_db
from utils.jwt import get_current_user
from datetime import datetime, timedelta
from typing import List, Dict
from services.redis_client import cache_key, redis_get_json, redis_set_json

router = APIRouter()
DASHBOARD_CACHE_TTL_SECONDS = 30


@router.get("/dashboard/summary")
def get_dashboard_summary(db: Session = Depends(get_db), user=Depends(get_current_user)):
    cache_id = cache_key("dashboard", "summary", user.id)
    cached = redis_get_json(cache_id)
    if isinstance(cached, dict):
        return cached

    agents = (
        db.query(
            models.Agent.id,
            models.Agent.name,
            models.Agent.instructions,
            models.Agent.model,
            models.Agent.avatar_url,
            models.Agent.created_at,
        )
        .filter(models.Agent.user_id == user.id)
        .order_by(models.Agent.created_at.desc())
        .limit(100)
        .all()
    )

    agent_rows = [
        {
            "id": str(agent.id),
            "name": agent.name,
            "instructions": agent.instructions,
            "model": agent.model,
            "avatar_url": agent.avatar_url,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
        }
        for agent in agents
    ]

    knowledge_count = (
        db.query(func.count(models.KnowledgeBase.id))
        .join(models.Agent, models.KnowledgeBase.agent_id == models.Agent.id)
        .filter(models.Agent.user_id == user.id)
        .scalar()
        or 0
    )

    next_reset = user.last_reset_date + timedelta(days=30)
    agent_usage = (
        db.query(
            models.Agent.id,
            models.Agent.name,
            func.sum(models.UsageLog.credits_used).label("total_used"),
        )
        .join(models.UsageLog, models.UsageLog.agent_id == models.Agent.id)
        .filter(
            models.UsageLog.user_id == user.id,
            models.UsageLog.timestamp >= user.last_reset_date,
        )
        .group_by(models.Agent.id, models.Agent.name)
        .all()
    )
    credits = {
        "user_type": user.user_type,
        "credits_remaining": user.credits_remaining,
        "max_credits": user.get_max_credits(),
        "next_reset_date": next_reset.isoformat(),
        "days_until_reset": (next_reset - datetime.utcnow()).days,
        "agent_usage": [
            {
                "agent_id": str(row.id),
                "agent_name": row.name,
                "credits_used": row.total_used or 0,
            }
            for row in agent_usage
        ],
    }

    agent_counts_query = (
        db.query(models.Agent.name, func.count(models.UsageLog.id).label("count"))
        .join(models.UsageLog, models.Agent.id == models.UsageLog.agent_id)
        .filter(models.UsageLog.user_id == user.id)
        .group_by(models.Agent.name)
        .all()
    )
    agent_counts = {name: count for name, count in agent_counts_query}
    total_questions = sum(agent_counts.values())
    interactions = {
        "total_questions": total_questions,
        "total_responses": total_questions,
        "most_active_agent": max(agent_counts, key=agent_counts.get) if agent_counts else None,
        "agent_interaction_counts": agent_counts,
    }

    logs = (
        db.query(
            models.UsageLog.timestamp,
            models.UsageLog.message_content,
            models.UsageLog.response_content,
            models.Agent.name.label('agent_name'),
        )
        .join(models.Agent, models.UsageLog.agent_id == models.Agent.id)
        .filter(models.UsageLog.user_id == user.id)
        .order_by(models.UsageLog.timestamp.desc())
        .limit(20)
        .all()
    )
    recent_activity = [
        {
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "agent_name": log.agent_name or "Unknown",
            "question": (log.message_content[:200] + "…") if log.message_content and len(log.message_content) > 200 else log.message_content,
            "response": (log.response_content[:200] + "…") if log.response_content and len(log.response_content) > 200 else log.response_content,
        }
        for log in logs
    ]

    hour_counts_query = (
        db.query(
            extract("hour", models.UsageLog.timestamp).label("hour"),
            func.count(models.UsageLog.id).label("count"),
        )
        .filter(models.UsageLog.user_id == user.id)
        .group_by(extract("hour", models.UsageLog.timestamp))
        .all()
    )
    hour_counts = {int(hour): count for hour, count in hour_counts_query}
    activity = {
        "recent_activity": recent_activity,
        "peak_usage_hour": max(hour_counts, key=hour_counts.get) if hour_counts else None,
        "hourly_activity": hour_counts,
    }

    payload = {
        "agents": agent_rows,
        "credits": credits,
        "interactions": interactions,
        "activity": activity,
        "knowledgeCount": knowledge_count,
    }
    redis_set_json(cache_id, payload, DASHBOARD_CACHE_TTL_SECONDS)
    return payload

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
        db.query(
            models.UsageLog.timestamp,
            models.UsageLog.message_content,
            models.UsageLog.response_content,
            models.Agent.name.label('agent_name'),
        )
        .join(models.Agent, models.UsageLog.agent_id == models.Agent.id)
        .filter(models.UsageLog.user_id == user.id)
        .order_by(models.UsageLog.timestamp.desc())
        .limit(20)
        .all()
    )

    recent_activity = [
        {
            "timestamp": log.timestamp,
            "agent_name": log.agent_name or "Unknown",
            "question": (log.message_content[:200] + "…") if log.message_content and len(log.message_content) > 200 else log.message_content,
            "response": (log.response_content[:200] + "…") if log.response_content and len(log.response_content) > 200 else log.response_content,
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
