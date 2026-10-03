"""Owner-facing Human Agent management, mounted under /owner/human-agents.

Requires the standard Supabase owner auth. Password hashes and invite tokens are
never returned to the client.

Invite flow: POST /owner/human-agents creates a human_agents row with status=invited,
generates an invite token, sends it via send_invite_email, and returns
{id, email, status, invite_link?}.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from db import models
from services.supabase_auth import get_db
from services.human_agent_auth import create_invite_token, hash_invite_token
from services.email_provider import send_invite_email
from utils.jwt import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()



class InviteRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(None, max_length=120)
    agent_ids: Optional[List[uuid.UUID]] = None


class AssignmentUpdate(BaseModel):
    agent_ids: List[uuid.UUID] = Field(..., description="Complete desired assignment set (replaces existing)")


class HumanAgentOut(BaseModel):
    id: str
    email: str
    name: Optional[str]
    status: str
    created_at: Optional[str]
    assignments: List[str] = Field(default_factory=list)  # agent_ids as strings

    class Config:
        from_attributes = True


def _to_out(ha: models.HumanAgent, assignments: Optional[List[models.AgentAssignment]] = None) -> dict:
    return {
        "id": str(ha.id),
        "email": ha.email,
        "name": ha.name,
        "status": ha.status,
        "created_at": ha.created_at.isoformat() if ha.created_at else None,
        "assignments": [str(a.agent_id) for a in (assignments or ha.assignments or [])],
    }



@router.post("", status_code=201)
def invite_human_agent(
    payload: InviteRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    email = payload.email.lower().strip()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        raise HTTPException(status_code=422, detail="Invalid email address")

    existing = db.query(models.HumanAgent).filter(
        models.HumanAgent.owner_user_id == user.id,
        models.HumanAgent.email == email,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A human agent with this email already exists for your account")

    token, expires = create_invite_token()
    ha = models.HumanAgent(
        owner_user_id=user.id,
        email=email,
        name=(payload.name or "").strip() or None,
        status="invited",
        invite_token=hash_invite_token(token),
        invite_token_expires=expires,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ha)
    db.commit()
    db.refresh(ha)

    if payload.agent_ids:
        # Validate ownership of each agent_id
        for aid in payload.agent_ids:
            agent = db.query(models.Agent).filter(models.Agent.id == aid, models.Agent.user_id == user.id).first()
            if not agent:
                # Roll back the human agent row on validation failure
                db.delete(ha)
                db.commit()
                raise HTTPException(status_code=404, detail=f"Agent {aid} not found or not owned by you")
        for aid in set(payload.agent_ids):
            db.add(models.AgentAssignment(human_agent_id=ha.id, agent_id=aid))
        db.commit()
        db.refresh(ha)

    try:
        send_invite_email(to_email=email, invite_token=token, inviter_email=user.email)
    except Exception:
        logger.exception("invite_email_failed human_agent_id=%s email=%s", ha.id, email)
        # Don't fail the invite if email fails in dev — token is still stored

    logger.info("human_agent_invited id=%s owner=%s email=%s", ha.id, user.id, email)

    # Only expose the invite token outside production, and only when explicitly enabled
    is_dev = (__import__("os").getenv("ENV") != "production") and (__import__("os").getenv("EXPOSE_INVITE_TOKEN", "1") == "1")
    resp = _to_out(ha)
    if is_dev:
        resp["invite_token"] = token  # type: ignore
        import os
        frontend = (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
        resp["invite_link"] = f"{frontend}/human-agent/accept-invite?token={token}"  # type: ignore
    return resp



@router.get("")
def list_human_agents(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agents = db.query(models.HumanAgent).filter(models.HumanAgent.owner_user_id == user.id).order_by(models.HumanAgent.created_at.desc()).all()
    return [_to_out(ha) for ha in agents]



@router.get("/{human_agent_id}")
def get_human_agent(
    human_agent_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        ha_uuid = uuid.UUID(human_agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Human agent not found")
    ha = db.query(models.HumanAgent).filter(
        models.HumanAgent.id == ha_uuid,
        models.HumanAgent.owner_user_id == user.id,
    ).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Human agent not found")
    return _to_out(ha)



@router.patch("/{human_agent_id}/assignments")
def update_assignments(
    human_agent_id: str,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        ha_uuid = uuid.UUID(human_agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Human agent not found")
    ha = db.query(models.HumanAgent).filter(
        models.HumanAgent.id == ha_uuid,
        models.HumanAgent.owner_user_id == user.id,
    ).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Human agent not found")

    # Validate all agent_ids belong to this owner
    desired = set(payload.agent_ids)
    for aid in desired:
        agent = db.query(models.Agent).filter(models.Agent.id == aid, models.Agent.user_id == user.id).first()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {aid} not found or not owned by you")

    # Replace: delete existing, insert desired
    old_ids = {r.agent_id for r in db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == ha.id).all()}
    db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == ha.id).delete()
    for aid in desired:
        db.add(models.AgentAssignment(human_agent_id=ha.id, agent_id=aid))
    db.commit()
    db.refresh(ha)
    # Invalidate the agent→humans cache for changed agents
    try:
        from services import handoff_service as _hs
        import asyncio
        affected = old_ids | desired
        for aid in affected:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(lambda a=aid: asyncio.ensure_future(_hs.invalidate_agent_human_cache(str(a))))
            except Exception:
                pass
    except Exception:
        pass
    logger.info("human_agent_assignments_updated id=%s count=%s", ha.id, len(desired))
    return _to_out(ha)


def _requeue_conversations_for_human(db: Session, human_agent_id: uuid.UUID):
    """Requeue every open conversation assigned to a human agent being removed/disabled."""
    from services import handoff_service
    from services.handoff_service import release_conversation
    convs = db.query(models.Conversation).filter(
        models.Conversation.assigned_human_agent_id == human_agent_id,
        models.Conversation.status == "human",
    ).all()
    for c in convs:
        try:
            release_conversation(db, c, reason="owner_remove")
        except Exception:
            c.status = "queued"
            c.assigned_human_agent_id = None
            c.updated_at = datetime.now(timezone.utc)
            db.commit()
        for c in convs:
            try:
                payload = {"type": "status_change", "status": "queued", "conversation_id": str(c.id)}
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.call_soon_threadsafe(lambda cc=c: asyncio.ensure_future(handoff_service.broadcast_to_conversation(str(cc.id), payload)))
                        loop.call_soon_threadsafe(lambda cc=c: asyncio.ensure_future(handoff_service.broadcast_to_humans_for_agent(cc.agent_id, {**payload, "agent_id": str(cc.agent_id)})))
                except Exception:
                    pass
            except Exception:
                pass
        logger.info("requeued_conversations_on_human_remove human_agent_id=%s count=%s", human_agent_id, len(convs))



class HumanAgentPatch(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    status: Optional[str] = Field(None, pattern="^(invited|active|disabled)$")


@router.patch("/{human_agent_id}")
def patch_human_agent(
    human_agent_id: str,
    payload: HumanAgentPatch,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        ha_uuid = uuid.UUID(human_agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Human agent not found")
    ha = db.query(models.HumanAgent).filter(
        models.HumanAgent.id == ha_uuid,
        models.HumanAgent.owner_user_id == user.id,
    ).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Human agent not found")
    if payload.name is not None:
        ha.name = payload.name.strip() or None
    if payload.status is not None:
        # Disabling requeues their open conversations first
        if payload.status == "disabled" and ha.status != "disabled":
            _requeue_conversations_for_human(db, ha.id)
        ha.status = payload.status
    db.commit()
    db.refresh(ha)
    return _to_out(ha)



@router.post("/{human_agent_id}/resend-invite")
def resend_invite(
    human_agent_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        ha_uuid = uuid.UUID(human_agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Human agent not found")
    ha = db.query(models.HumanAgent).filter(
        models.HumanAgent.id == ha_uuid,
        models.HumanAgent.owner_user_id == user.id,
    ).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Human agent not found")
    if ha.status == "active":
        raise HTTPException(status_code=400, detail="Human agent is already active")
    token, expires = create_invite_token()
    ha.invite_token = hash_invite_token(token)
    ha.invite_token_expires = expires
    ha.status = "invited"
    db.commit()
    try:
        send_invite_email(to_email=ha.email, invite_token=token, inviter_email=user.email)
    except Exception:
        logger.exception("resend_invite_email_failed id=%s", ha.id)
    logger.info("human_agent_invite_resent id=%s", ha.id)
    resp = _to_out(ha)
    import os
    if os.getenv("ENV") != "production" and os.getenv("EXPOSE_INVITE_TOKEN", "1") == "1":
        resp["invite_token"] = token  # type: ignore
        frontend = (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
        resp["invite_link"] = f"{frontend}/human-agent/accept-invite?token={token}"  # type: ignore
    return resp



@router.delete("/{human_agent_id}")
def delete_human_agent(
    human_agent_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        ha_uuid = uuid.UUID(human_agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Human agent not found")
    ha = db.query(models.HumanAgent).filter(
        models.HumanAgent.id == ha_uuid,
        models.HumanAgent.owner_user_id == user.id,
    ).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Human agent not found")
    # Requeue before deleting
    _requeue_conversations_for_human(db, ha.id)
    db.delete(ha)
    db.commit()
    logger.info("human_agent_deleted id=%s owner=%s", ha_uuid, user.id)
    return {"ok": True}
