"""
Human-agent API (§2, §4, §5, §8).

Mounted under /human-agent . All routes except /auth/* require a
human-agent JWT (role=human_agent) via get_current_human_agent.

Concepts:
  - Listing is scoped to assigned AI agents via the join in §2.
  - Claiming sets assigned_human_agent_id + status=human (only if queued).
  - Sending a message inserts a ChatMessage (sender_type=human_agent) and
    broadcasts to the visitor WS via handoff_service + sends a fallback
    email via email_provider.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session, joinedload

from db import models
from services.supabase_auth import get_db
from services.human_agent_auth import (
    create_human_agent_jwt,
    get_current_human_agent,
    hash_password,
    verify_password,
)
from services import handoff_service
from services.presence import (
    human_agent_connected,
    human_agent_disconnected,
    is_any_human_online_for_agent_sync,
)
from services.email_provider import send_human_reply_email, send_queued_fallback_email

logger = logging.getLogger(__name__)

router = APIRouter()
auth_router = APIRouter()
# We'll mount auth_router under /human-agent/auth and `router` under /human-agent

# ── Schemas ──────────────────────────────────────────────────────────────────

class AcceptInviteRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=256)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _conversation_out(conv: models.Conversation, include_messages: bool = False, db: Session | None = None) -> dict:
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
        rows = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.session_id == conv.session_id)
            .order_by(models.ChatMessage.created_at.asc())
            .all()
        )
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
    elif include_messages:
        base["messages"] = []
    return base


def _require_assignment(db: Session, human_agent: models.HumanAgent, conv: models.Conversation) -> None:
    """Enforce §2 authorization rule."""
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
    """Gate on notified_at (§5 step 4)."""
    if not conv.visitor_email:
        return False
    if conv.notified_at is None:
        return True
    # Stale threshold: 30 minutes
    age = datetime.now(timezone.utc) - conv.notified_at.replace(tzinfo=timezone.utc) if conv.notified_at.tzinfo is None else datetime.now(timezone.utc) - conv.notified_at
    return age > timedelta(minutes=30)


async def _maybe_send_queued_fallback(db: Session, conv: models.Conversation) -> None:
    """Called after conversation transitions to `queued`. Implements §5."""
    if conv.status != "queued":
        return
    if not _should_send_fallback(conv):
        return
    # Check presence
    if is_any_human_online_for_agent_sync(db, conv.agent_id):
        logger.info("fallback_skipped_human_online conversation_id=%s agent_id=%s", conv.id, conv.agent_id)
        return
    # Send email
    try:
        agent = db.query(models.Agent).filter(models.Agent.id == conv.agent_id).first()
        agent_name = agent.name if agent else None
        send_queued_fallback_email(to_email=conv.visitor_email, conversation_id=str(conv.id), agent_name=agent_name)
        conv.notified_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("fallback_email_sent conversation_id=%s to=%s", conv.id, conv.visitor_email)
    except Exception:
        logger.exception("fallback_email_failed conversation_id=%s", conv.id)


# ── Auth: accept-invite ──────────────────────────────────────────────────────

@auth_router.post("/accept-invite")
def accept_invite(payload: AcceptInviteRequest, db: Session = Depends(get_db)):
    token = payload.token.strip()
    ha = db.query(models.HumanAgent).filter(models.HumanAgent.invite_token == token).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")
    if ha.status == "active":
        raise HTTPException(status_code=400, detail="Invite already accepted. Please log in.")
    # Check expiry
    if ha.invite_token_expires and ha.invite_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite link has expired. Ask the account owner to resend it.")
    if ha.status == "disabled":
        raise HTTPException(status_code=403, detail="This invite has been disabled")
    # Set password
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
def invite_status(token: str = Query(..., min_length=10), db: Session = Depends(get_db)):
    ha = db.query(models.HumanAgent).filter(models.HumanAgent.invite_token == token).first()
    if not ha:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    expired = bool(ha.invite_token_expires and ha.invite_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc))
    return {
        "email": ha.email,
        "name": ha.name,
        "status": ha.status,
        "expired": expired,
        "expires_at": ha.invite_token_expires.isoformat() if ha.invite_token_expires else None,
    }


# ── Auth: login ──────────────────────────────────────────────────────────────

@auth_router.post("/login")
def human_agent_login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    # Lookup by email (case-insensitive). If multiple owners share same email, pick the first active one.
    # For stricter isolation, the invite email could be owner-scoped, but login can't know owner yet.
    candidates = db.query(models.HumanAgent).filter(models.HumanAgent.email == email).all()
    if not candidates:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # Prefer active; if multiple active, use most recent
    active = [c for c in candidates if c.status == "active" and c.password_hash]
    if not active:
        # Give specific error for invited-but-not-yet-accepted
        invited = [c for c in candidates if c.status == "invited"]
        if invited:
            raise HTTPException(status_code=403, detail="Invite not yet accepted. Please use the invite link to set your password first.")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # If multiple active (same email under different owners — rare), try password against each
    matched: models.HumanAgent | None = None
    for cand in sorted(active, key=lambda x: x.created_at or datetime.min, reverse=True):
        if cand.password_hash and verify_password(payload.password, cand.password_hash):
            matched = cand
            break
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


# ── Me ───────────────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(human_agent: models.HumanAgent = Depends(get_current_human_agent), db: Session = Depends(get_db)):
    assignments = db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == human_agent.id).all()
    # Resolve agent names for convenience
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


# ── Agents assigned to this human agent (for switcher) ───────────────────────

@router.get("/agents")
def list_assigned_agents(human_agent: models.HumanAgent = Depends(get_current_human_agent), db: Session = Depends(get_db)):
    rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == human_agent.id).all()
    if not rows:
        return []
    agent_ids = [r.agent_id for r in rows]
    agents = db.query(models.Agent).filter(models.Agent.id.in_(agent_ids)).all()
    return [{"id": str(a.id), "name": a.name, "avatar_url": a.avatar_url, "created_at": a.created_at.isoformat() if a.created_at else None} for a in agents]


# ── Conversations list ───────────────────────────────────────────────────────

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


# ── Conversation detail ──────────────────────────────────────────────────────

@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
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
    return _conversation_out(conv, include_messages=True, db=db)


# ── Claim ────────────────────────────────────────────────────────────────────

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
    conv = db.query(models.Conversation).filter(models.Conversation.id == cid).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    _require_assignment(db, human_agent, conv)

    if conv.status == "resolved":
        raise HTTPException(status_code=400, detail="Conversation is already resolved")
    if conv.status == "human":
        if conv.assigned_human_agent_id == human_agent.id:
            return _conversation_out(conv)
        raise HTTPException(status_code=409, detail="Conversation already claimed by another agent")
    if conv.status not in ("queued", "collecting_email", "bot"):
        # Allow claiming from queued only per spec, but be lenient for collecting_email with email present
        if conv.status != "queued":
            raise HTTPException(status_code=400, detail=f"Cannot claim conversation in '{conv.status}' status")

    # Perform transition
    from services.handoff_service import transition_status

    # Need to run transition_status in thread if db session is used elsewhere? It's sync.
    # Wrap in asyncio.to_thread to avoid blocking? Keep sync for now.
    transition_status(db, conv, "human", human_agent=human_agent, notify=True)

    # Also fan-out via presence-aware broadcast for human ws
    await handoff_service.broadcast_to_conversation(str(conv.id), {
        "type": "agent_claimed",
        "agent_name": human_agent.name or human_agent.email,
        "conversation_id": str(conv.id),
        "human_agent_id": str(human_agent.id),
    })
    # Also send a system message?
    # Add ChatMessage system note
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


# ── Send message ─────────────────────────────────────────────────────────────

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

    # Insert ChatMessage
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
    # Broadcast to visitor WS (and any human ws listening on same conversation channel)
    await handoff_service.broadcast_to_conversation(str(conv.id), payload)
    # Also fan-out to any other human dashboards assigned to this AI agent (§4 live updates)
    try:
        await handoff_service.broadcast_to_humans_for_agent(conv.agent_id, payload)
    except Exception:
        logger.exception("human_message_human_broadcast_failed conversation_id=%s", conv.id)

    # Also pg_notify for multi-instance
    try:
        handoff_service.pg_notify(str(conv.id), {
            "type": "message",
            "sender_type": "human_agent",
            "sender_name": human_agent.name or human_agent.email,
            "content": content,
            "conversation_id": str(conv.id),
        })
    except Exception:
        pass

    # §5: send transactional email to visitor with reply + link back
    if conv.visitor_email:
        try:
            agent = db.query(models.Agent).filter(models.Agent.id == conv.agent_id).first()
            send_human_reply_email(
                to_email=conv.visitor_email,
                reply_text=content,
                conversation_id=str(conv.id),
                agent_name=agent.name if agent else None,
                from_name=human_agent.name or human_agent.email,
            )
            logger.info("human_reply_email_sent conversation_id=%s to=%s", conv.id, conv.visitor_email)
        except Exception:
            logger.exception("human_reply_email_failed conversation_id=%s", conv.id)

    logger.info("human_message_sent conversation_id=%s human_agent_id=%s", conv.id, human_agent.id)
    return {
        "id": msg.id,
        "content": msg.content,
        "sender_type": msg.sender_type,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


# ── Resolve ──────────────────────────────────────────────────────────────────

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


# ── WebSocket for human agents ───────────────────────────────────────────────

@router.websocket("/ws")
async def human_agent_ws(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """
    Live updates for all conversations assigned to this human agent.

    Auth: Bearer token via header OR `?token=<jwt>` query param.
    Upon connect, registers presence. Broadcasts all conversation events
    (status_change, message, resolved) for the agent's assigned conversations.

    For simplicity, the client subscribes implicitly to every conversation
    whose agent_id is in their assignment set — no explicit subscribe message
    needed. :contentReference[oaicite:0]{index=0}
    """
    # Resolve token from header or query
    token = None
    auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    # Verify JWT
    from services.human_agent_auth import decode_human_agent_jwt
    try:
        payload = decode_human_agent_jwt(token)
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
    ha = db.query(models.HumanAgent).filter(models.HumanAgent.id == ha_uuid).first()
    if not ha or ha.status != "active":
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await human_agent_connected(str(ha.id))
    logger.info("human_agent_ws_connected id=%s email=%s", ha.id, ha.email)

    # Determine which conversations to listen to: all conversation_ids for assigned agents
    assigned_agent_ids = [r.agent_id for r in db.query(models.AgentAssignment).filter(models.AgentAssignment.human_agent_id == ha.id).all()]

    # Human registry: this single queue receives all events for this human's assigned agents
    # (new queued conversations, status changes, messages). This is what gives the dashboard
    # its live Queued/Active/Resolved tabs without needing per-conversation subscribe.
    human_q = await handoff_service.register_human_ws(str(ha.id))

    # Also subscribe to per-conversation channels for existing open conversations
    # (so messages sent directly to conversation_id reach this socket as well,
    # and to support the optional client-side `subscribe` message for detail view)
    from services.handoff_service import _ws_registry, _registry_lock

    subscribed_conv_ids: set[str] = set()

    async def _subscribe_to_conversation(conv_id: str):
        if conv_id in subscribed_conv_ids:
            return
        async with _registry_lock:
            _ws_registry.setdefault(conv_id, set()).add(human_q)
        subscribed_conv_ids.add(conv_id)

    if assigned_agent_ids:
        existing = db.query(models.Conversation.id).filter(
            models.Conversation.agent_id.in_(assigned_agent_ids),
            models.Conversation.status != "resolved",
        ).all()
        for (cid,) in existing:
            await _subscribe_to_conversation(str(cid))

    # Send initial snapshot so dashboard can populate without REST round-trip
    try:
        await websocket.send_json({
            "type": "connected",
            "human_agent_id": str(ha.id),
            "assigned_agent_ids": [str(x) for x in assigned_agent_ids],
        })
    except Exception:
        # Client already disconnected (e.g. React StrictMode double-mount) — clean up and exit
        await handoff_service.unregister_human_ws(str(ha.id), human_q)
        async with _registry_lock:
            for cid in list(subscribed_conv_ids):
                bucket = _ws_registry.get(cid)
                if bucket:
                    bucket.discard(human_q)
                    if not bucket:
                        _ws_registry.pop(cid, None)
        await human_agent_disconnected(str(ha.id))
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Also send current presence / counts if needed
    # Heartbeat
    ping_interval = 25

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
                # Handle client messages: ping/pong, subscribe, etc.
                msg_type = data.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "subscribe" and data.get("conversation_id"):
                    cid = str(data["conversation_id"])
                    # Validate assignment before subscribing
                    try:
                        cid_u = uuid.UUID(cid)
                        conv = db.query(models.Conversation).filter(models.Conversation.id == cid_u).first()
                        if conv and conv.agent_id in assigned_agent_ids:
                            await _subscribe_to_conversation(cid)
                            # Send current state
                            await websocket.send_json({
                                "type": "status_change",
                                "status": conv.status,
                                "conversation_id": cid,
                            })
                    except Exception:
                        pass
                elif msg_type == "pong":
                    pass
            except asyncio.TimeoutError:
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
        # Unsubscribe from all per-conversation buckets
        async with _registry_lock:
            for cid in list(subscribed_conv_ids):
                bucket = _ws_registry.get(cid)
                if bucket:
                    bucket.discard(human_q)
                    if not bucket:
                        _ws_registry.pop(cid, None)
        # Unregister from global human registry
        await handoff_service.unregister_human_ws(str(ha.id), human_q)
        await human_agent_disconnected(str(ha.id))
        logger.info("human_agent_ws_disconnected id=%s", ha.id)

    try:
        await websocket.close()
    except Exception:
        pass
