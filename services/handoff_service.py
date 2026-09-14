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
    """
    channel = f"conversation_{conversation_id}"
    payload_str = json.dumps(payload)
    try:
        with engine.connect() as conn:
            # Use raw DBAPI execute for NOTIFY (not a DML statement)
            conn.connection.cursor().execute(  # type: ignore[attr-defined]
                f"NOTIFY {channel}, %s", (payload_str,)
            )
            conn.connection.commit()  # type: ignore[attr-defined]
    except Exception:
        logger.exception("pg_notify_failed conversation_id=%s", conversation_id)


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
        asyncio.get_event_loop().call_soon_threadsafe(
            lambda: asyncio.ensure_future(
                broadcast_to_conversation(str(conv.id), payload)
            )
        )


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
