from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from db import schemas
from api.auth.auth import get_db
from db import models
from utils.jwt import get_current_user
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from uuid import UUID

router = APIRouter()


@router.get("/{agent_id}/analytics/overview")
def get_agent_analytics_overview(
    agent_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get comprehensive analytics overview: total conversations, messages, credits, and active time periods
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Use SQL aggregations instead of loading all logs into memory
    total_stats = db.query(
        func.count(models.UsageLog.id).label('total_messages'),
        func.sum(models.UsageLog.credits_used).label('total_credits')
    ).filter(
        models.UsageLog.agent_id == agent_id,
        models.UsageLog.timestamp >= start_date
    ).first()
    
    total_messages = total_stats.total_messages or 0
    total_credits = total_stats.total_credits or 0
    
    if total_messages == 0:
        return {
            "agent_id": str(agent_id),
            "agent_name": agent.name,
            "period_days": days,
            "total_messages": 0,
            "total_credits_used": 0,
            "avg_messages_per_day": 0,
            "most_active_day": None,
            "most_active_hour": None,
            "daily_breakdown": [],
            "hourly_distribution": {}
        }
    
    # Daily breakdown using SQL GROUP BY
    daily_results = db.query(
        func.date(models.UsageLog.timestamp).label('date'),
        func.count(models.UsageLog.id).label('message_count'),
        func.sum(models.UsageLog.credits_used).label('credits_used')
    ).filter(
        models.UsageLog.agent_id == agent_id,
        models.UsageLog.timestamp >= start_date
    ).group_by(func.date(models.UsageLog.timestamp)).all()
    
    daily_stats = {
        str(row.date): {
            "date": str(row.date),
            "message_count": row.message_count,
            "credits_used": float(row.credits_used or 0)
        }
        for row in daily_results
    }
    
    # Hourly distribution using SQL GROUP BY
    hourly_results = db.query(
        func.extract('hour', models.UsageLog.timestamp).label('hour'),
        func.count(models.UsageLog.id).label('count')
    ).filter(
        models.UsageLog.agent_id == agent_id,
        models.UsageLog.timestamp >= start_date
    ).group_by(func.extract('hour', models.UsageLog.timestamp)).all()
    
    hourly_stats = {int(row.hour): row.count for row in hourly_results}
    
    most_active_day = max(daily_stats.items(), key=lambda x: x[1]["message_count"])[0] if daily_stats else None
    most_active_hour = max(hourly_stats.items(), key=lambda x: x[1])[0] if hourly_stats else None
    
    return {
        "agent_id": str(agent_id),
        "agent_name": agent.name,
        "period_days": days,
        "total_messages": total_messages,
        "total_credits_used": total_credits,
        "avg_messages_per_day": round(total_messages / days, 2),
        "most_active_day": most_active_day,
        "most_active_hour": f"{most_active_hour}:00" if most_active_hour is not None else None,
        "daily_breakdown": sorted(daily_stats.values(), key=lambda x: x["date"], reverse=True),
        "hourly_distribution": hourly_stats
    }


@router.get("/{agent_id}/analytics/conversations")
def get_agent_conversations(
    agent_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_content: bool = Query(True, description="Include full message/response content"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get recent conversations with pagination, returns message content, timestamps, and credits used
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get total count for pagination
    total_count = db.query(models.UsageLog).filter(
        models.UsageLog.agent_id == agent_id
    ).count()
    
    # Get paginated logs - optimize by excluding large text fields if not needed
    if include_content:
        logs = db.query(models.UsageLog).filter(
            models.UsageLog.agent_id == agent_id
        ).order_by(desc(models.UsageLog.timestamp)).offset(offset).limit(limit).all()
        
        conversations = [{
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "message": log.message_content,
            "response": log.response_content,
            "credits_used": log.credits_used
        } for log in logs]
    else:
        # Only load metadata without large text fields for better performance
        logs = db.query(
            models.UsageLog.id,
            models.UsageLog.timestamp,
            models.UsageLog.credits_used
        ).filter(
            models.UsageLog.agent_id == agent_id
        ).order_by(desc(models.UsageLog.timestamp)).offset(offset).limit(limit).all()
        
        conversations = [{
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "credits_used": log.credits_used
        } for log in logs]
    
    return {
        "agent_id": str(agent_id),
        "agent_name": agent.name,
        "total_conversations": total_count,
        "page": offset // limit + 1,
        "page_size": limit,
        "conversations": conversations
    }


@router.get("/{agent_id}/analytics/performance")
def get_agent_performance_metrics(
    agent_id: UUID,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get performance metrics: message volume trends, peak patterns, and growth comparison with previous period
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    previous_start = start_date - timedelta(days=days)
    
    # Use COUNT aggregations instead of loading all logs
    current_stats = db.query(
        func.count(models.UsageLog.id).label('count'),
        func.sum(models.UsageLog.credits_used).label('credits')
    ).filter(
        models.UsageLog.agent_id == agent_id,
        models.UsageLog.timestamp >= start_date
    ).first()
    
    previous_stats = db.query(
        func.count(models.UsageLog.id).label('count'),
        func.sum(models.UsageLog.credits_used).label('credits')
    ).filter(
        models.UsageLog.agent_id == agent_id,
        models.UsageLog.timestamp >= previous_start,
        models.UsageLog.timestamp < start_date
    ).first()
    
    current_count = current_stats.count or 0
    previous_count = previous_stats.count or 0
    current_credits = float(current_stats.credits or 0)
    previous_credits = float(previous_stats.credits or 0)
    
    # Calculate growth
    growth_rate = 0
    if previous_count > 0:
        growth_rate = ((current_count - previous_count) / previous_count) * 100
    
    # Weekly breakdown using SQL GROUP BY for efficiency
    weekly_results = db.query(
        func.extract('year', models.UsageLog.timestamp).label('year'),
        func.extract('week', models.UsageLog.timestamp).label('week'),
        func.count(models.UsageLog.id).label('message_count'),
        func.sum(models.UsageLog.credits_used).label('credits_used')
    ).filter(
        models.UsageLog.agent_id == agent_id,
        models.UsageLog.timestamp >= start_date
    ).group_by(
        func.extract('year', models.UsageLog.timestamp),
        func.extract('week', models.UsageLog.timestamp)
    ).all()
    
    weekly_stats = [
        {
            "week": f"{int(row.year)}-W{int(row.week):02d}",
            "message_count": row.message_count,
            "credits_used": float(row.credits_used or 0)
        }
        for row in weekly_results
    ]
    
    return {
        "agent_id": str(agent_id),
        "agent_name": agent.name,
        "period_days": days,
        "current_period": {
            "messages": current_count,
            "credits": current_credits
        },
        "previous_period": {
            "messages": previous_count,
            "credits": previous_credits
        },
        "growth_rate_percent": round(growth_rate, 2),
        "weekly_breakdown": sorted(weekly_stats, key=lambda x: x["week"], reverse=True)
    }


@router.get("/{agent_id}/analytics/knowledge-base")
def get_agent_kb_analytics(
    agent_id: UUID,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get KB analytics: total KBs, chunks, storage, status breakdown, and source type distribution
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get all KBs for this agent
    kbs = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.agent_id == agent_id
    ).all()
    
    if not kbs:
        return {
            "agent_id": str(agent_id),
            "agent_name": agent.name,
            "total_kbs": 0,
            "total_chunks": 0,
            "total_storage_bytes": 0,
            "status_breakdown": {},
            "source_type_breakdown": {},
            "knowledge_bases": []
        }
    
    # Calculate metrics
    total_chunks = sum(kb.chunk_count or 0 for kb in kbs)
    total_storage = sum((kb.file_size_bytes or 0) + (kb.extracted_size_bytes or 0) for kb in kbs)
    
    status_breakdown = {}
    source_type_breakdown = {}
    
    for kb in kbs:
        # Status breakdown
        status = kb.status.value
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        # Source type breakdown
        source = kb.source_type.value
        source_type_breakdown[source] = source_type_breakdown.get(source, 0) + 1
    
    kb_details = [{
        "kb_id": str(kb.id),
        "title": kb.title or kb.original_filename,
        "source_type": kb.source_type.value,
        "status": kb.status.value,
        "chunk_count": kb.chunk_count or 0,
        "file_size_bytes": kb.file_size_bytes or 0,
        "created_at": kb.created_at.isoformat() if kb.created_at else None
    } for kb in kbs]
    
    return {
        "agent_id": str(agent_id),
        "agent_name": agent.name,
        "total_kbs": len(kbs),
        "total_chunks": total_chunks,
        "total_storage_bytes": total_storage,
        "total_storage_mb": round(total_storage / (1024 * 1024), 2),
        "status_breakdown": status_breakdown,
        "source_type_breakdown": source_type_breakdown,
        "knowledge_bases": kb_details
    }


@router.get("/{agent_id}/activity")
def get_agent_activity_log(
    agent_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get recent activity: conversation logs, KB additions/modifications, and configuration changes
    # Verify agent ownership
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    activity = []
    
    # Optimize: Get recent conversations with limited fields only
    recent_conversations = db.query(
        models.UsageLog.timestamp,
        models.UsageLog.message_content,
        models.UsageLog.credits_used
    ).filter(
        models.UsageLog.agent_id == agent_id
    ).order_by(desc(models.UsageLog.timestamp)).limit(limit // 2).all()
    
    for conv in recent_conversations:
        activity.append({
            "type": "conversation",
            "timestamp": conv.timestamp.isoformat(),
            "details": {
                "message_preview": conv.message_content[:100] if conv.message_content else None,
                "credits_used": conv.credits_used
            }
        })
    
    # Get recent KB additions with limited fields
    recent_kbs = db.query(
        models.KnowledgeBase.id,
        models.KnowledgeBase.created_at,
        models.KnowledgeBase.title,
        models.KnowledgeBase.original_filename,
        models.KnowledgeBase.source_type,
        models.KnowledgeBase.status
    ).filter(
        models.KnowledgeBase.agent_id == agent_id
    ).order_by(desc(models.KnowledgeBase.created_at)).limit(limit // 2).all()
    
    for kb in recent_kbs:
        activity.append({
            "type": "kb_added",
            "timestamp": kb.created_at.isoformat() if kb.created_at else None,
            "details": {
                "kb_id": str(kb.id),
                "title": kb.title or kb.original_filename,
                "source_type": kb.source_type.value,
                "status": kb.status.value
            }
        })
    
    # Sort all activities by timestamp
    activity.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    
    return {
        "agent_id": str(agent_id),
        "agent_name": agent.name,
        "total_activities": len(activity),
        "activities": activity[:limit]
    }
