from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from db.database import BackgroundSession, engine
from db import models

logger = logging.getLogger(__name__)

# ── In-process WebSocket registry ─────────────────────────────────────────────
# Maps conversation_id (str) → set of asyncio.Queue objects.
# Each connected WebSocket has one Queue; the WS handler drains it.
_ws_registry: Dict[str, Set[asyncio.Queue]] = {}
_registry_lock = asyncio.Lock()

# ── Human-agent dashboard registry ─────────────────────────────────────────
# Maps human_agent_id (str) → set of dashboard WebSocket queues.
# Unlike conversation registry (visitor side), human agents subscribe to
# *all* events for conversation IDs belonging to their assigned AI agents.
# When a new queued conversation is created, we fan-out to every online human
# who is assigned to that AI agent, even though they never explicitly
# subscribed to that conversation_id. This gives the dashboard its live
# Queued/Active updates.
_human_registry: Dict[str, Set[asyncio.Queue]] = {}
_human_lock = asyncio.Lock()


async def register_human_ws(human_agent_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=128)
    async with _human_lock:
        _human_registry.setdefault(human_agent_id, set()).add(q)
    return q


async def unregister_human_ws(human_agent_id: str, q: asyncio.Queue) -> None:
    async with _human_lock:
        bucket = _human_registry.get(human_agent_id)
        if bucket:
            bucket.discard(q)
            if not bucket:
                del _human_registry[human_agent_id]


async def broadcast_to_humans_for_agent(agent_id: uuid.UUID | str, payload: dict) -> None:
    """
    Push payload to every dashboard WebSocket whose human_agent is assigned to `agent_id`.
    Queries assignment via BackgroundSession so callers don't need a live Session.
    Also supports direct human_agent_id broadcast via caller passing human_agent_id set.
    """
    agent_id_str = str(agent_id)
    # Snapshot human queues without holding lock during DB query
    async with _human_lock:
        all_humans = list(_human_registry.items())  # (human_id, set(queues))
    if not all_humans:
        return
    # Find which humans are assigned to this agent
    try:
        from db.database import BackgroundSession as BG
        db = BG()
        try:
            # Query assignments for this agent
            rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.agent_id == uuid.UUID(agent_id_str)).all()
            assigned = {str(r.human_agent_id) for r in rows}
        finally:
            db.close()
    except Exception:
        logger.exception("broadcast_to_humans_query_failed agent_id=%s", agent_id_str)
        return
    if not assigned:
        return
    queues: list[asyncio.Queue] = []
    async with _human_lock:
        for hid, qs in _human_registry.items():
            if hid in assigned:
                queues.extend(list(qs))
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("human_ws_queue_full agent_id=%s", agent_id_str)


async def register_ws(conversation_id: str) -> asyncio.Queue:
    """Register a new WebSocket listener for a conversation. Returns its queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=64)
    async with _registry_lock:
        _ws_registry.setdefault(conversation_id, set()).add(q)
    return q


async def unregister_ws(conversation_id: str, q: asyncio.Queue) -> None:
    async with _registry_lock:
        bucket = _ws_registry.get(conversation_id)
        if bucket:
            bucket.discard(q)
            if not bucket:
                del _ws_registry[conversation_id]


async def broadcast_to_conversation(conversation_id: str, payload: dict) -> None:
    """Push a payload to every WebSocket queue registered for this conversation."""
    async with _registry_lock:
        queues = list(_ws_registry.get(conversation_id, set()))
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("handoff_ws_queue_full conversation_id=%s", conversation_id)


# ── Postgres NOTIFY helper ─────────────────────────────────────────────────────

def pg_notify(conversation_id: str, payload: dict) -> None:
    """
    Issue a synchronous NOTIFY on the conversation channel.
    Called inside the same DB transaction as the write that triggered it.
    Uses a raw psycopg2 connection from the engine pool.

    Channel names are sanitized (hyphens → underscores) and quoted to avoid
    Postgres identifier syntax errors — UUIDs contain hyphens which are not
    valid bare identifiers.
    """
    raw = f"conversation_{conversation_id}"
    # sanitize: replace hyphens with underscores; keep alphanumeric + underscore only
    channel = "".join(c if c.isalnum() or c == "_" else "_" for c in raw)
    payload_str = json.dumps(payload)
    try:
        with engine.connect() as conn:
            # Use quoted identifier so underscores + alphanum are safe
            # Use psycopg2 mogrify via cursor.execute with identifier quoting manually
            conn.connection.cursor().execute(  # type: ignore[attr-defined]
                f'NOTIFY "{channel}", %s', (payload_str,)
            )
            conn.connection.commit()  # type: ignore[attr-defined]
    except Exception:
        logger.exception("pg_notify_failed conversation_id=%s channel=%s", conversation_id, channel)


# ── Conversation helpers ───────────────────────────────────────────────────────

def get_or_create_conversation(
    db: Session,
    *,
    agent_id: uuid.UUID,
    deployment_id: int,
    session_id: uuid.UUID,
    visitor_id: str,
) -> models.Conversation:
    """
    Return the existing open Conversation for this session, or create one.
    A session can only have one non-resolved conversation at a time.
    """
    conv = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.session_id == session_id,
            models.Conversation.status != "resolved",
        )
        .first()
    )
    if conv:
        return conv

    conv = models.Conversation(
        agent_id=agent_id,
        deployment_id=deployment_id,
        session_id=session_id,
        visitor_id=visitor_id,
        status="bot",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    logger.info("conversation_created id=%s agent_id=%s", conv.id, agent_id)
    return conv


def transition_status(
    db: Session,
    conv: models.Conversation,
    new_status: str,
    *,
    visitor_email: Optional[str] = None,
    human_agent: Optional[models.HumanAgent] = None,
    notify: bool = True,
    check_email_fallback: bool = False,
) -> None:
    """
    Advance the conversation state machine and optionally pg_notify.

    Valid transitions:
        bot → collecting_email
        bot | collecting_email → queued
        queued → human
        human | queued → resolved
    """
    old_status = conv.status
    conv.status = new_status
    conv.updated_at = datetime.now(timezone.utc)

    if visitor_email and not conv.visitor_email:
        conv.visitor_email = visitor_email

    if human_agent and new_status == "human":
        conv.assigned_human_agent_id = human_agent.id

    db.commit()

    payload: dict[str, Any] = {
        "type": "status_change",
        "status": new_status,
        "conversation_id": str(conv.id),
    }
    if human_agent:
        payload["agent_name"] = human_agent.name or human_agent.email

    logger.info(
        "conversation_status_change id=%s %s→%s",
        conv.id, old_status, new_status,
    )

    if notify:
        pg_notify(str(conv.id), payload)
        # Also fan-out in-process (same instance, no round-trip)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        broadcast_to_conversation(str(conv.id), payload)
                    )
                )
                # Also notify human-agent dashboards assigned to this AI agent (§4 live updates)
                # Fire-and-forget; human ws registry will fan-out even for new queued conversations
                try:
                    loop.call_soon_threadsafe(
                        lambda: asyncio.ensure_future(
                            broadcast_to_humans_for_agent(conv.agent_id, {**payload, "agent_id": str(conv.agent_id)})
                        )
                    )
                except Exception:
                    logger.exception("human_broadcast_schedule_failed conversation_id=%s", conv.id)
            else:
                pass
        except RuntimeError:
            pass

    # §5 email fallback — fire-and-forget after commit (only for queued)
    if check_email_fallback and new_status == "queued":
        try:
            _maybe_check_email_fallback_sync(db, conv)
        except Exception:
            logger.exception("email_fallback_check_failed conversation_id=%s", conv.id)


def _maybe_check_email_fallback_sync(db: Session, conv: models.Conversation) -> None:
    """Sync helper for fallback email gate (§5). Called after transition to queued."""
    from datetime import timedelta

    # Gate on notified_at (§5 step 4)
    if not conv.visitor_email:
        return
    if conv.notified_at is not None:
        try:
            age = datetime.now(timezone.utc) - (conv.notified_at.replace(tzinfo=timezone.utc) if conv.notified_at.tzinfo is None else conv.notified_at)
            if age < timedelta(minutes=30):
                logger.info("fallback_gated_recent conversation_id=%s age_min=%.1f", conv.id, age.total_seconds()/60)
                return
        except Exception:
            pass

    # Presence check — is any human assigned to this AI agent currently online?
    try:
        from services.presence import is_any_human_online_for_agent_sync
        if is_any_human_online_for_agent_sync(db, conv.agent_id):
            logger.info("fallback_skipped_human_online conversation_id=%s agent_id=%s", conv.id, conv.agent_id)
            return
    except Exception:
        logger.exception("presence_check_failed conversation_id=%s", conv.id)
        # If presence check fails, err on side of sending email

    try:
        from services.email_provider import send_queued_fallback_email
        agent = db.query(models.Agent).filter(models.Agent.id == conv.agent_id).first()
        agent_name = agent.name if agent else None
        ok = send_queued_fallback_email(to_email=conv.visitor_email, conversation_id=str(conv.id), agent_name=agent_name)
        if ok:
            conv.notified_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("fallback_email_sent conversation_id=%s to=%s", conv.id, conv.visitor_email)
    except Exception:
        logger.exception("fallback_email_send_failed conversation_id=%s", conv.id)


# ── transfer_to_human tool definition ─────────────────────────────────────────

TRANSFER_TO_HUMAN_TOOL = {
    "type": "function",
    "function": {
        "name": "transfer_to_human",
        "description": (
            "Transfer this conversation to a human support agent. "
            "Call this when the user explicitly asks to speak with a human, "
            "when you cannot resolve their issue, or when the situation requires "
            "human judgment. Provide a brief reason."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason for the transfer (shown to the human agent).",
                }
            },
            "required": ["reason"],
        },
    },
}


def build_handoff_ack_message(agent_display_name: str) -> str:
    """The user-facing message the bot sends when handing off."""
    return (
        "I'm connecting you with a member of our team — hang tight! "
        "They'll be with you shortly. 🙌"
    )
