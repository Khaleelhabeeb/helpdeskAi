"""Owner team analytics and conversation viewer: overview, conversation list and detail."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from db import models
from services.supabase_auth import get_db
from utils.jwt import get_current_user

router = APIRouter()


def _owner_agent_ids(db: Session, owner_user_id: int):
    rows = db.query(models.Agent.id).filter(models.Agent.user_id == owner_user_id).all()
    return [r[0] for r in rows]


@router.get("/analytics")
def team_analytics(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent_ids = _owner_agent_ids(db, user.id)
    if not agent_ids:
        return {
            "total": 0,
            "by_status": {},
            "cases_closed": 0,
            "active": 0,
            "queued": 0,
            "human": 0,
            "by_human": [],
            "by_agent": [],
            "recent": [],
        }

    by_status_q = db.query(models.Conversation.status, func.count(models.Conversation.id)).filter(
        models.Conversation.agent_id.in_(agent_ids)
    ).group_by(models.Conversation.status).all()
    by_status = {s: c for s, c in by_status_q}
    total = sum(by_status.values())
    cases_closed = by_status.get("resolved", 0)
    queued = by_status.get("queued", 0)
    human = by_status.get("human", 0)
    active = queued + human

    human_agents = db.query(models.HumanAgent).filter(models.HumanAgent.owner_user_id == user.id).all()
    by_human = []
    for ha in human_agents:
        # Conversations assigned to this human
        q = db.query(models.Conversation).filter(models.Conversation.assigned_human_agent_id == ha.id)
        total_ha = q.count()
        by_status_ha = {s: c for s, c in db.query(models.Conversation.status, func.count(models.Conversation.id)).filter(models.Conversation.assigned_human_agent_id == ha.id).group_by(models.Conversation.status).all()}
        by_human.append({
            "id": str(ha.id),
            "email": ha.email,
            "name": ha.name,
            "status": ha.status,
            "total": total_ha,
            "queued": by_status_ha.get("queued", 0),
            "human": by_status_ha.get("human", 0),
            "resolved": by_status_ha.get("resolved", 0),
            "collecting_email": by_status_ha.get("collecting_email", 0),
        })

    by_agent = []
    for aid in agent_ids:
        ag = db.query(models.Agent).filter(models.Agent.id == aid).first()
        if not ag:
            continue
        by_status_ag = {s: c for s, c in db.query(models.Conversation.status, func.count(models.Conversation.id)).filter(models.Conversation.agent_id == aid).group_by(models.Conversation.status).all()}
        by_agent.append({
            "id": str(ag.id),
            "name": ag.name,
            "total": sum(by_status_ag.values()),
            "by_status": by_status_ag,
        })

    recent = db.query(models.Conversation).filter(models.Conversation.agent_id.in_(agent_ids)).order_by(models.Conversation.updated_at.desc()).limit(10).options(joinedload(models.Conversation.assigned_human_agent)).all()
    recent_out = []
    for c in recent:
        recent_out.append({
            "id": str(c.id),
            "agent_id": str(c.agent_id),
            "status": c.status,
            "visitor_id": c.visitor_id,
            "visitor_email": c.visitor_email,
            "assigned_human_agent_id": str(c.assigned_human_agent_id) if c.assigned_human_agent_id else None,
            "assigned_human_name": c.assigned_human_agent.name or c.assigned_human_agent.email if c.assigned_human_agent else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {
        "total": total,
        "by_status": by_status,
        "cases_closed": cases_closed,
        "active": active,
        "queued": queued,
        "human": human,
        "by_human": by_human,
        "by_agent": by_agent,
        "recent": recent_out,
    }


@router.get("/conversations")
def list_team_conversations(
    status: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    human_agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent_ids = _owner_agent_ids(db, user.id)
    if not agent_ids:
        return {"conversations": [], "total": 0}

    q = db.query(models.Conversation).filter(models.Conversation.agent_id.in_(agent_ids))

    if status:
        if status not in ("bot", "collecting_email", "queued", "human", "resolved"):
            raise HTTPException(status_code=422, detail="Invalid status")
        q = q.filter(models.Conversation.status == status)
    if agent_id:
        try:
            aid = uuid.UUID(agent_id)
            if aid not in agent_ids:
                raise HTTPException(status_code=403, detail="Not your agent")
            q = q.filter(models.Conversation.agent_id == aid)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid agent_id")
    if human_agent_id:
        try:
            hid = uuid.UUID(human_agent_id)
            # Verify human belongs to owner
            ha = db.query(models.HumanAgent).filter(models.HumanAgent.id == hid, models.HumanAgent.owner_user_id == user.id).first()
            if not ha:
                raise HTTPException(status_code=404, detail="Human agent not found")
            q = q.filter(models.Conversation.assigned_human_agent_id == hid)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid human_agent_id")

    total = q.count()
    rows = q.order_by(models.Conversation.updated_at.desc()).offset(offset).limit(limit).options(joinedload(models.Conversation.assigned_human_agent)).all()
    out = []
    for c in rows:
        preview = None
        if c.session_id:
            last = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == c.session_id).order_by(models.ChatMessage.created_at.desc()).first()
            if last:
                preview = last.content[:120]
        out.append({
            "id": str(c.id),
            "agent_id": str(c.agent_id),
            "status": c.status,
            "visitor_id": c.visitor_id,
            "visitor_email": c.visitor_email,
            "assigned_human_agent_id": str(c.assigned_human_agent_id) if c.assigned_human_agent_id else None,
            "assigned_human_name": c.assigned_human_agent.name or c.assigned_human_agent.email if c.assigned_human_agent else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "preview": preview,
        })
    return {"conversations": out, "total": total, "limit": limit, "offset": offset}


@router.get("/conversations/{conversation_id}")
def get_team_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    agent_ids = _owner_agent_ids(db, user.id)
    conv = db.query(models.Conversation).filter(models.Conversation.id == cid, models.Conversation.agent_id.in_(agent_ids)).options(joinedload(models.Conversation.assigned_human_agent)).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = []
    if conv.session_id:
        rows = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == conv.session_id).order_by(models.ChatMessage.created_at.asc()).all()
        for r in rows:
            msgs.append({
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "sender_type": r.sender_type,
                "sender_id": str(r.sender_id) if r.sender_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
    return {
        "id": str(conv.id),
        "agent_id": str(conv.agent_id),
        "status": conv.status,
        "visitor_id": conv.visitor_id,
        "visitor_email": conv.visitor_email,
        "assigned_human_agent_id": str(conv.assigned_human_agent_id) if conv.assigned_human_agent_id else None,
        "assigned_human_name": conv.assigned_human_agent.name or conv.assigned_human_agent.email if conv.assigned_human_agent else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": msgs,
    }
