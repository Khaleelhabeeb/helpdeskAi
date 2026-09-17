"""Human-agent API mounted under /human-agent.

Every route except /auth/* requires a human-agent JWT (role=human_agent) via
get_current_human_agent; listings are scoped to the caller's assigned AI agents.
"""
import asyncio
import contextlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session, joinedload

from db import models
from db.database import SessionLocal, BackgroundSession
from services.supabase_auth import get_db
from services.human_agent_auth import (
    create_human_agent_jwt,
    get_current_human_agent,
    hash_password,
    verify_password,
    verify_password_with_dummy,
    find_human_by_invite_token,
)
from services import handoff_service
from services.presence import (
    human_agent_connected,
    human_agent_disconnected,
    human_agent_heartbeat,
    is_any_human_online_for_agent_sync,
)
from services.email_provider import send_human_reply_email, send_queued_fallback_email
from utils.rate_limit import create_limiter

logger = logging.getLogger(__name__)
limiter = create_limiter()
# One fallback email per conversation per 5 minutes (in-memory; use Redis for multi-worker)
_email_debounce: dict[str, float] = {}

router = APIRouter()
auth_router = APIRouter()


class AcceptInviteRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)



def _conversation_out(conv: models.Conversation, include_messages: bool = False, db: Session | None = None, message_limit: int = 50, message_after_id: int | None = None) -> dict:
    base = {
        "id": str(conv.id),
        "agent_id": str(conv.agent_id),
        "deployment_id": conv.deployment_id,
        "session_id": str(conv.session_id) if conv.session_id else None,
        "visitor_id": conv.visitor_id,
        "visitor_email": conv.visitor_email,
        "status": conv.status,
        "assigned_human_agent_id": str(conv.assigned_human_agent_id) if conv.assigned_human_agent_id else None,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "notified_at": conv.notified_at.isoformat() if conv.notified_at else None,
    }
    if conv.assigned_human_agent:
        base["assigned_human_agent_name"] = conv.assigned_human_agent.name or conv.assigned_human_agent.email
    if include_messages and db is not None and conv.session_id:
        q = db.query(models.ChatMessage).filter(models.ChatMessage.session_id == conv.session_id)
        if message_after_id is not None:
            q = q.filter(models.ChatMessage.id > message_after_id)
        rows = q.order_by(models.ChatMessage.created_at.asc()).limit(min(message_limit, 100)).all()
        base["messages"] = [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "sender_type": r.sender_type,
                "sender_id": str(r.sender_id) if r.sender_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        base["messages_has_more"] = len(rows) == min(message_limit, 100)
    elif include_messages:
        base["messages"] = []
    return base


def _require_assignment(db: Session, human_agent: models.HumanAgent, conv: models.Conversation) -> None:
    # conv.agent_id must be in human_agent's assignments
    exists = (
        db.query(models.AgentAssignment)
        .filter(
            models.AgentAssignment.human_agent_id == human_agent.id,
            models.AgentAssignment.agent_id == conv.agent_id,
        )
        .first()
    )
    if not exists:
        raise HTTPException(status_code=403, detail="You are not assigned to this agent's conversations")


def _should_send_fallback(conv: models.Conversation) -> bool:
    if not conv.visitor_email:
        return False
    if conv.notified_at is None:
        return True
    # Stale threshold: 30 minutes
    age = datetime.now(timezone.utc) - conv.notified_at.replace(tzinfo=timezone.utc) if conv.notified_at.tzinfo is None else datetime.now(timezone.utc) - conv.notified_at
    return age > timedelta(minutes=30)


async def _maybe_send_queued_fallback(db: Session, conv: models.Conversation) -> None:
    """Called after a conversation transitions to queued."""
    if conv.status != "queued":
        return
    if not _should_send_fallback(conv):
        return
    if is_any_human_online_for_agent_sync(db, conv.agent_id):
        logger.info("fallback_skipped_human_online conversation_id=%s agent_id=%s", conv.id, conv.agent_id)
        return
    try:
        agent = db.query(models.Agent).filter(models.Agent.id == conv.agent_id).first()
        agent_name = agent.name if agent else None
        send_queued_fallback_email(to_email=conv.visitor_email, conversation_id=str(conv.id), agent_name=agent_name)
        conv.notified_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("fallback_email_sent conversation_id=%s to=%s", conv.id, conv.visitor_email)
    except Exception:
        logger.exception("fallback_email_failed conversation_id=%s", conv.id)



@auth_router.post("/accept-invite")
@limiter.limit("5/minute")
def accept_invite(payload: AcceptInviteRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    token = payload.token.strip()
    ha = find_human_by_invite_token(db, token)
    if not ha:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")
    if ha.status == "active":
        raise HTTPException(status_code=400, detail="Invite already accepted. Please log in.")
    if ha.invite_token_expires and ha.invite_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite link has expired. Ask the account owner to resend it.")
    if ha.status == "disabled":
        raise HTTPException(status_code=403, detail="This invite has been disabled")
    try:
        ha.password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.name and payload.name.strip():
        ha.name = payload.name.strip()
    ha.status = "active"
    ha.invite_token = None
    ha.invite_token_expires = None
    db.commit()
    db.refresh(ha)
    logger.info("human_agent_activated id=%s email=%s", ha.id, ha.email)
    # Return JWT immediately so frontend can redirect to dashboard without second login
    token_jwt = create_human_agent_jwt(ha)
    return {
        "access_token": token_jwt,
        "token_type": "bearer",
        "human_agent": {
            "id": str(ha.id),
            "email": ha.email,
            "name": ha.name,
            "owner_user_id": ha.owner_user_id,
        },
    }


# Also accept GET for debugging invite validity (optional)
@auth_router.get("/invite-status")
@limiter.limit("10/minute")
def invite_status(request: Request, response: Response, token: str = Query(..., min_length=10), db: Session = Depends(get_db)):
    ha = find_human_by_invite_token(db, token)
    if not ha:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    expired = bool(ha.invite_token_expires and ha.invite_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc))
    # Never return the invite token; keep the payload minimal
    return {
        "email": ha.email,
        "name": ha.name,
        "status": ha.status,
        "expired": expired,
        "expires_at": ha.invite_token_expires.isoformat() if ha.invite_token_expires else None,
    }



@auth_router.post("/login")
@limiter.limit("5/minute")
def human_agent_login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    candidates = db.query(models.HumanAgent).filter(models.HumanAgent.email == email).all()
    if not candidates:
        # Always burn a bcrypt compare so a missing user is not detectable by timing
        verify_password_with_dummy(payload.password, None)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # The same email may exist under several owners; require disambiguation
    distinct_owners = {c.owner_user_id for c in candidates if c.status == "active"}
    if len(distinct_owners) > 1:
        matches = [c for c in candidates if c.status == "active" and c.password_hash and verify_password(payload.password, c.password_hash)]
        if len(matches) == 1:
            matched = matches[0]
            jwt_token = create_human_agent_jwt(matched)
            logger.warning("cross_tenant_login_single_match email=%s owners=%s chosen=%s", email, distinct_owners, matched.owner_user_id)
            return {
                "access_token": jwt_token,
                "token_type": "bearer",
                "human_agent": {"id": str(matched.id), "email": matched.email, "name": matched.name, "owner_user_id": matched.owner_user_id},
            }
        elif len(matches) > 1:
            # Multiple tenants have same email+password — ambiguous
            logger.warning("cross_tenant_login_ambiguous email=%s owners=%s", email, distinct_owners)
            raise HTTPException(status_code=409, detail="This email exists in multiple workspaces with same password. Please contact owner for a distinct login link.")
        else:
            # no match
            raise HTTPException(status_code=401, detail="Invalid email or password")

    active = [c for c in candidates if c.status == "active" and c.password_hash]
    if not active:
        invited = [c for c in candidates if c.status == "invited"]
        if invited:
            raise HTTPException(status_code=403, detail="Invite not yet accepted. Please use the invite link to set your password first.")
        verify_password_with_dummy(payload.password, None)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    matched: models.HumanAgent | None = None
    for cand in sorted(active, key=lambda x: x.created_at or datetime.min, reverse=True):
        if cand.password_hash and verify_password(payload.password, cand.password_hash):
            matched = cand
            break
        else:
            pass
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    jwt_token = create_human_agent_jwt(matched)
    logger.info("human_agent_login id=%s email=%s owner=%s", matched.id, matched.email, matched.owner_user_id)
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "human_agent": {
            "id": str(matched.id),
            "email": matched.email,
            "name": matched.name,
            "owner_user_id": matched.owner_user_id,
        },
    }



@router.get("/me")
def get_me(human_agent: models.HumanAgent = Depends(get_current_human_agent), db: Session = Depends(get_db)):
    assignments = db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == human_agent.id).all()
    agent_ids = [a.agent_id for a in assignments]
    agents = []
    if agent_ids:
        rows = db.query(models.Agent).filter(models.Agent.id.in_(agent_ids)).all()
        agents = [{"id": str(r.id), "name": r.name, "avatar_url": r.avatar_url} for r in rows]
    return {
        "id": str(human_agent.id),
        "email": human_agent.email,
        "name": human_agent.name,
        "owner_user_id": human_agent.owner_user_id,
        "status": human_agent.status,
        "assignments": assignments and [str(a.agent_id) for a in assignments] or [],
        "agents": agents,
    }


@router.get("/ws-ticket")
def get_ws_ticket(human_agent: models.HumanAgent = Depends(get_current_human_agent)):
    from services.human_agent_auth import create_ws_ticket
    ticket = create_ws_ticket(human_agent)
    return {"ticket": ticket, "expires_in": 60}



@router.get("/agents")
def list_assigned_agents(human_agent: models.HumanAgent = Depends(get_current_human_agent), db: Session = Depends(get_db)):
    rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == human_agent.id).all()
    if not rows:
        return []
    agent_ids = [r.agent_id for r in rows]
    agents = db.query(models.Agent).filter(models.Agent.id.in_(agent_ids)).all()
    return [{"id": str(a.id), "name": a.name, "avatar_url": a.avatar_url, "created_at": a.created_at.isoformat() if a.created_at else None} for a in agents]



@router.get("/conversations")
def list_conversations(
    status: Optional[str] = Query(None, description="Filter: queued|human|resolved|collecting_email|bot|active. 'active' = human"),
    agent_id: Optional[str] = Query(None, description="Filter by AI agent id"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    human_agent: models.HumanAgent = Depends(get_current_human_agent),
    db: Session = Depends(get_db),
):
    # Scoped to assigned agents via join (falls out naturally if zero assignments)
    assigned_ids_q = db.query(models.AgentAssignment.agent_id).filter(models.AgentAssignment.human_agent_id == human_agent.id)
    assigned_ids = [r[0] for r in assigned_ids_q.all()]
    if not assigned_ids:
        return {"conversations": [], "total": 0}

    q = db.query(models.Conversation).filter(models.Conversation.agent_id.in_(assigned_ids))

    if agent_id:
        try:
            aid = uuid.UUID(agent_id)
            if aid not in assigned_ids:
                raise HTTPException(status_code=403, detail="Not assigned to this agent")
            q = q.filter(models.Conversation.agent_id == aid)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid agent_id")

    if status:
        # Normalize: frontend may send `active` meaning human
        if status == "active":
            status = "human"
        if status not in ("bot", "collecting_email", "queued", "human", "resolved"):
            raise HTTPException(status_code=422, detail="Invalid status filter")
        q = q.filter(models.Conversation.status == status)

    total = q.count()
    convs = q.order_by(models.Conversation.updated_at.desc()).offset(offset).limit(limit).options(joinedload(models.Conversation.assigned_human_agent)).all()
    return {
        "conversations": [_conversation_out(c) for c in convs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }



@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    after_id: int | None = Query(None, description="Cursor pagination: return messages with id > after_id"),
    human_agent: models.HumanAgent = Depends(get_current_human_agent),
    db: Session = Depends(get_db),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = db.query(models.Conversation).options(joinedload(models.Conversation.assigned_human_agent)).filter(models.Conversation.id == cid).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _require_assignment(db, human_agent, conv)
    return _conversation_out(conv, include_messages=True, db=db, message_limit=limit, message_after_id=after_id)



@router.post("/conversations/{conversation_id}/claim")
async def claim_conversation(
    conversation_id: str,
    human_agent: models.HumanAgent = Depends(get_current_human_agent),
    db: Session = Depends(get_db),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Load conv first to check assignment (requires read)
    conv_check = db.query(models.Conversation).filter(models.Conversation.id == cid).first()
    if not conv_check:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _require_assignment(db, human_agent, conv_check)

    if conv_check.status == "resolved":
        raise HTTPException(status_code=400, detail="Conversation is already resolved")
    if conv_check.status == "human":
        if conv_check.assigned_human_agent_id == human_agent.id:
            return _conversation_out(conv_check)
        raise HTTPException(status_code=409, detail="Conversation already claimed by another agent")

    # H1: atomic conditional update
    from services.handoff_service import atomic_claim_conversation

    conv = atomic_claim_conversation(db, cid, human_agent)
    # Single fan-out: broadcast_to_conversation reaches the visitor and subscribed humans
    await handoff_service.broadcast_to_conversation(str(conv.id), {
        "type": "status_change",
        "status": "human",
        "conversation_id": str(conv.id),
        "agent_name": human_agent.name or human_agent.email,
        "human_agent_id": str(human_agent.id),
    })
    await handoff_service.broadcast_to_humans_for_agent(conv.agent_id, {
        "type": "status_change",
        "status": "human",
        "conversation_id": str(conv.id),
        "agent_id": str(conv.agent_id),
        "agent_name": human_agent.name or human_agent.email,
        "human_agent_id": str(human_agent.id),
    })
    # Also send a system message
    if conv.session_id:
        try:
            db.add(models.ChatMessage(
                session_id=conv.session_id,
                role="assistant",
                content=f"{human_agent.name or human_agent.email} joined the conversation.",
                sender_type="system",
                created_at=datetime.now(timezone.utc),
            ))
            db.commit()
        except Exception:
            logger.exception("claim_system_message_failed conversation_id=%s", conv.id)

    logger.info("conversation_claimed id=%s by=%s", conv.id, human_agent.id)
    db.refresh(conv)
    return _conversation_out(conv)



@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    request: Request,
    human_agent: models.HumanAgent = Depends(get_current_human_agent),
    db: Session = Depends(get_db),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = db.query(models.Conversation).filter(models.Conversation.id == cid).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _require_assignment(db, human_agent, conv)

    if conv.status == "resolved":
        raise HTTPException(status_code=400, detail="Conversation is resolved — cannot send messages")
    if conv.status != "human":
        raise HTTPException(status_code=409, detail=f"Conversation must be in 'human' status to reply (current: {conv.status})")
    if conv.assigned_human_agent_id != human_agent.id:
        raise HTTPException(status_code=403, detail="You have not claimed this conversation")

    if not conv.session_id:
        raise HTTPException(status_code=500, detail="Conversation has no session")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content is required")

    msg = models.ChatMessage(
        session_id=conv.session_id,
        role="assistant",
        content=content,
        sender_type="human_agent",
        sender_id=human_agent.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    payload = {
        "type": "message",
        "sender_type": "human_agent",
        "sender_name": human_agent.name or human_agent.email,
        "sender_id": str(human_agent.id),
        "content": content,
        "conversation_id": str(conv.id),
        "message_id": msg.id,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "agent_id": str(conv.agent_id),
    }
    # Single fan-out: no separate broadcast_to_humans_for_agent, so nothing is delivered twice
    await handoff_service.broadcast_to_conversation(str(conv.id), payload)

    # Debounced fallback email, sent off the event loop
    if conv.visitor_email:
        now = time.time()
        last = _email_debounce.get(str(conv.id), 0)
        should_send = (now - last) > 300
        if should_send:
            _email_debounce[str(conv.id)] = now
            try:
                agent = db.query(models.Agent).filter(models.Agent.id == conv.agent_id).first()
                agent_name = agent.name if agent else None
                # Blocking Brevo call, run in a worker thread
                try:
                    await asyncio.to_thread(
                        send_human_reply_email,
                        to_email=conv.visitor_email,
                        reply_text=content,
                        conversation_id=str(conv.id),
                        agent_name=agent_name,
                        from_name=human_agent.name or human_agent.email,
                    )
                    logger.info("human_reply_email_sent conversation_id=%s to=%s", conv.id, conv.visitor_email)
                except Exception:
                    logger.exception("human_reply_email_failed conversation_id=%s", conv.id)
            except Exception:
                logger.exception("human_reply_email_prepare_failed conversation_id=%s", conv.id)
        else:
            logger.info("human_reply_email_debounced conversation_id=%s age=%.0fs", conv.id, now - last)

    logger.info("human_message_sent conversation_id=%s human_agent_id=%s", conv.id, human_agent.id)
    return {
        "id": msg.id,
        "content": msg.content,
        "sender_type": msg.sender_type,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }



@router.post("/conversations/{conversation_id}/resolve")
async def resolve_conversation(
    conversation_id: str,
    human_agent: models.HumanAgent = Depends(get_current_human_agent),
    db: Session = Depends(get_db),
):
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = db.query(models.Conversation).filter(models.Conversation.id == cid).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _require_assignment(db, human_agent, conv)

    if conv.status == "resolved":
        return _conversation_out(conv)
    if conv.status not in ("human", "queued"):
        raise HTTPException(status_code=400, detail=f"Cannot resolve conversation in '{conv.status}' status")
    # Only assignee can resolve if in human state
    if conv.status == "human" and conv.assigned_human_agent_id and conv.assigned_human_agent_id != human_agent.id:
        raise HTTPException(status_code=403, detail="Only the assigned agent can resolve this conversation")

    from services.handoff_service import transition_status
    transition_status(db, conv, "resolved", notify=True)
    await handoff_service.broadcast_to_conversation(str(conv.id), {
        "type": "resolved",
        "conversation_id": str(conv.id),
    })
    if conv.session_id:
        try:
            db.add(models.ChatMessage(
                session_id=conv.session_id,
                role="assistant",
                content="Conversation resolved.",
                sender_type="system",
                created_at=datetime.now(timezone.utc),
            ))
            db.commit()
        except Exception:
            logger.exception("resolve_system_message_failed conversation_id=%s", conv.id)

    logger.info("conversation_resolved id=%s by=%s", conv.id, human_agent.id)
    db.refresh(conv)
    return _conversation_out(conv)



@router.websocket("/ws")
async def human_agent_ws(
    websocket: WebSocket,
):
    """
    Live updates for every conversation assigned to this human agent.

    No DB session is held for the socket lifetime: auth happens in a scoped
    SessionLocal during the handshake.

    Auth: Authorization header, Sec-WebSocket-Protocol, or ?token (legacy, deprecated).
    JWT (iss/aud) or a short-lived ws_ticket (aud=human_agent_ws) is accepted. The
    socket is closed after 90s without a pong.
    """
    # Handshake auth happens in a scoped session
    # Prefer Sec-WebSocket-Protocol token, then Authorization, then query param
    token = None
    # Sec-WebSocket-Protocol: client may send "Bearer, <token>" or just token
    proto = websocket.headers.get("sec-websocket-protocol") or websocket.headers.get("Sec-WebSocket-Protocol")
    if proto:
        # Could be comma-separated; pick last token-like part
        for part in [p.strip() for p in proto.split(",")][::-1]:
            if len(part) > 20 and "." in part:
                token = part
                break
            if part.lower().startswith("bearer "):
                token = part[7:].strip()
                break
    if not token:
        auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    # Verify JWT — try human_agent audience first, then ws ticket audience
    from services.human_agent_auth import decode_human_agent_jwt
    payload = None
    for aud in ("human_agent_ws", "human_agent"):
        try:
            payload = decode_human_agent_jwt(token, audience=aud)
            break
        except HTTPException:
            continue
    if payload is None:
        try:
            payload = decode_human_agent_jwt(token)  # legacy fallback
        except HTTPException:
            await websocket.close(code=4401)
            return
    if payload.get("role") != "human_agent":
        await websocket.close(code=4403)
        return
    try:
        ha_uuid = uuid.UUID(str(payload.get("human_agent_id") or payload.get("sub")))
    except Exception:
        await websocket.close(code=4401)
        return
    # Scoped DB lookup — do not hold session
    ha = None
    assigned_agent_ids: list[uuid.UUID] = []
    try:
        with SessionLocal() as db:
            ha_row = db.query(models.HumanAgent).filter(models.HumanAgent.id == ha_uuid).first()
            if not ha_row or ha_row.status != "active":
                await websocket.close(code=4401)
                return
            # need ha info after session close
            ha = ha_row
            ha_id = str(ha_row.id)
            ha_email = ha_row.email
            ha_name = ha_row.name
            rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == ha_row.id).all()
            assigned_agent_ids = [r.agent_id for r in rows]
            # For presence warm cache
            cache_ids = {str(aid) for aid in assigned_agent_ids}
            # we can't await inside with, so schedule after
    except Exception:
        logger.exception("human_ws_handshake_failed")
        await websocket.close(code=1011)
        return
    if ha is None:
        await websocket.close(code=4401)
        return

    # Handshake done — accept and register presence
    try:
        # Warm the agent→humans cache
        for aid in assigned_agent_ids:
            try:
                # fire-and-forget cache warm (best effort)
                import asyncio as _a
                # need running loop
                try:
                    loop0 = asyncio.get_running_loop()
                    loop0.create_task(handoff_service.warm_agent_human_cache(str(aid), {ha_id}))
                except RuntimeError:
                    pass
            except Exception:
                pass
    except Exception:
        pass

    await websocket.accept()
    # Echo Sec-WebSocket-Protocol back to the client
    await human_agent_connected(ha_id)
    logger.info("human_agent_ws_connected id=%s email=%s", ha_id, ha_email)

    # Human registry: this single queue receives all events for this human's assigned agents
    human_q = await handoff_service.register_human_ws(ha_id)

    from services.handoff_service import _ws_registry, _registry_lock

    subscribed_conv_ids: set[str] = set()

    async def _subscribe_to_conversation(conv_id: str):
        if conv_id in subscribed_conv_ids:
            return
        async with _registry_lock:
            _ws_registry.setdefault(conv_id, set()).add(human_q)
        subscribed_conv_ids.add(conv_id)

    if assigned_agent_ids:
        # Query with a fresh scoped session
        try:
            with SessionLocal() as db2:
                existing = db2.query(models.Conversation.id).filter(
                    models.Conversation.agent_id.in_(assigned_agent_ids),
                    models.Conversation.status != "resolved",
                ).all()
                for (cid,) in existing:
                    await _subscribe_to_conversation(str(cid))
        except Exception:
            logger.exception("human_ws_subscribe_init_failed")

    # Send initial snapshot so dashboard can populate without REST round-trip
    try:
        await websocket.send_json({
            "type": "connected",
            "human_agent_id": ha_id,
            "assigned_agent_ids": [str(x) for x in assigned_agent_ids],
        })
    except Exception:
        await handoff_service.unregister_human_ws(ha_id, human_q)
        async with _registry_lock:
            for cid in list(subscribed_conv_ids):
                bucket = _ws_registry.get(cid)
                if bucket:
                    bucket.discard(human_q)
                    if not bucket:
                        _ws_registry.pop(cid, None)
        await human_agent_disconnected(ha_id)
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Heartbeat + pong deadline
    ping_interval = 25
    pong_deadline_seconds = 90
    last_pong = asyncio.get_event_loop().time()

    async def _pump():
        while True:
            msg = await human_q.get()
            try:
                await websocket.send_json(msg)
            except Exception:
                break

    pump_task = asyncio.create_task(_pump())

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=ping_interval)
                msg_type = data.get("type") if isinstance(data, dict) else None
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    last_pong = asyncio.get_event_loop().time()
                    await human_agent_heartbeat(ha_id)
                elif msg_type == "pong":
                    last_pong = asyncio.get_event_loop().time()
                    await human_agent_heartbeat(ha_id)
                elif msg_type == "subscribe" and data.get("conversation_id"):
                    cid = str(data["conversation_id"])
                    try:
                        cid_u = uuid.UUID(cid)
                        with SessionLocal() as db3:
                            conv = db3.query(models.Conversation).filter(models.Conversation.id == cid_u).first()
                            if conv and conv.agent_id in assigned_agent_ids:
                                await _subscribe_to_conversation(cid)
                                await websocket.send_json({
                                    "type": "status_change",
                                    "status": conv.status,
                                    "conversation_id": cid,
                                })
                    except Exception:
                        pass
                    last_pong = asyncio.get_event_loop().time()
                    await human_agent_heartbeat(ha_id)
                else:
                    last_pong = asyncio.get_event_loop().time()
                    await human_agent_heartbeat(ha_id)
            except asyncio.TimeoutError:
                # Check pong deadline before sending ping
                if asyncio.get_event_loop().time() - last_pong > pong_deadline_seconds:
                    logger.info("human_agent_ws_pong_timeout id=%s", ha_id)
                    break
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        async with _registry_lock:
            for cid in list(subscribed_conv_ids):
                bucket = _ws_registry.get(cid)
                if bucket:
                    bucket.discard(human_q)
                    if not bucket:
                        _ws_registry.pop(cid, None)
        await handoff_service.unregister_human_ws(ha_id, human_q)
        await human_agent_disconnected(ha_id)
        logger.info("human_agent_ws_disconnected id=%s", ha_id)

    try:
        await websocket.close()
    except Exception:
        pass
