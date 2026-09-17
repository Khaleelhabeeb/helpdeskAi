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

# conversation_id (str) → set of per-connection queues; each WS handler drains its own
_ws_registry: Dict[str, Set[asyncio.Queue]] = {}
_registry_lock = asyncio.Lock()

# human_agent_id (str) → dashboard WebSocket queues. Unlike the visitor registry,
# humans are fanned out to for every conversation of their assigned AI agents.
_human_registry: Dict[str, Set[asyncio.Queue]] = {}
_human_lock = asyncio.Lock()

# agent_id → assigned human_agent_ids; invalidated when assignments change
_agent_to_humans_cache: Dict[str, Set[str]] = {}
_agent_cache_lock = asyncio.Lock()


async def invalidate_agent_human_cache(agent_id: str | None = None):
    async with _agent_cache_lock:
        if agent_id:
            _agent_to_humans_cache.pop(str(agent_id), None)
        else:
            _agent_to_humans_cache.clear()


async def warm_agent_human_cache(agent_id: str, human_ids: Set[str]):
    async with _agent_cache_lock:
        _agent_to_humans_cache[str(agent_id)] = set(human_ids)


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
    """Push to every dashboard whose human_agent is assigned to `agent_id` (cache-first)."""
    agent_id_str = str(agent_id)
    async with _human_lock:
        all_humans = list(_human_registry.items())
    if not all_humans:
        return
    # Try cache first
    assigned: Set[str] | None = None
    async with _agent_cache_lock:
        cached = _agent_to_humans_cache.get(agent_id_str)
        if cached is not None:
            assigned = set(cached)
    if assigned is None:
        # Cache miss — small sync query
        try:
            from db.database import BackgroundSession as BG
            db = BG()
            try:
                rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.agent_id == uuid.UUID(agent_id_str)).all()
                assigned = {str(r.human_agent_id) for r in rows}
                async with _agent_cache_lock:
                    _agent_to_humans_cache[agent_id_str] = set(assigned)
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
    async with _registry_lock:
        queues = list(_ws_registry.get(conversation_id, set()))
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("handoff_ws_queue_full conversation_id=%s", conversation_id)


# Best-effort NOTIFY, disabled unless ENABLE_PG_NOTIFY=1. Nothing in this codebase
# LISTENs, so it is currently a no-op kept for future multi-instance fan-out; payloads
# are truncated to stay under the 8 kB Postgres NOTIFY limit.
def pg_notify(conversation_id: str, payload: dict) -> None:
    import os as _os
    if _os.getenv("ENABLE_PG_NOTIFY", "0") != "1":
        return
    raw = f"conversation_{conversation_id}"
    channel = "".join(c if c.isalnum() or c == "_" else "_" for c in raw)
    payload_str = json.dumps(payload)
    if len(payload_str.encode("utf-8")) > 7500:
        # Too large to NOTIFY: send a refetch signal instead
        payload_str = json.dumps({"type": payload.get("type", "unknown"), "conversation_id": str(conversation_id), "truncated": True})
    try:
        with engine.connect() as conn:
            conn.connection.cursor().execute(  # type: ignore[attr-defined]
                f'NOTIFY "{channel}", %s', (payload_str,)
            )
            conn.connection.commit()  # type: ignore[attr-defined]
    except Exception:
        logger.exception("pg_notify_failed conversation_id=%s channel=%s", conversation_id, channel)


def get_or_create_conversation(
    db: Session,
    *,
    agent_id: uuid.UUID,
    deployment_id: int,
    session_id: uuid.UUID,
    visitor_id: str,
) -> models.Conversation:
    """Return the session's open Conversation, creating one if there is none."""
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
    Advance the conversation state machine and notify subscribers.

    Valid transitions: bot → collecting_email|queued, collecting_email → queued,
    queued → human|resolved, human → resolved.
    """
    valid = {
        "bot": {"collecting_email", "queued"},
        "collecting_email": {"queued"},
        "queued": {"human", "resolved"},
        "human": {"resolved"},
    }
    old_status = conv.status
    # same-status calls are idempotent no-ops
    if old_status != new_status and new_status not in valid.get(old_status, set()):
        logger.warning("invalid_transition id=%s %s→%s", conv.id, old_status, new_status)
        # Lenient by design: log only, never raise
        pass
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
        # Use get_running_loop for thread-safety (instead of get_event_loop)
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(broadcast_to_conversation(str(conv.id), payload))
            )
            try:
                loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        broadcast_to_humans_for_agent(conv.agent_id, {**payload, "agent_id": str(conv.agent_id)})
                    )
                )
            except Exception:
                logger.exception("human_broadcast_schedule_failed conversation_id=%s", conv.id)
        except RuntimeError:
            # No running loop (e.g., in sync test or BackgroundSession thread) — try fallback
            try:
                loop2 = asyncio.get_event_loop()
                if loop2.is_running():
                    loop2.call_soon_threadsafe(lambda: asyncio.ensure_future(broadcast_to_conversation(str(conv.id), payload)))
                    loop2.call_soon_threadsafe(lambda: asyncio.ensure_future(broadcast_to_humans_for_agent(conv.agent_id, {**payload, "agent_id": str(conv.agent_id)})))
            except RuntimeError:
                pass
        # pg_notify is a no-op unless ENABLE_PG_NOTIFY=1
        try:
            pg_notify(str(conv.id), payload)
        except Exception:
            pass

    # Fire-and-forget fallback email after commit, queued only
    if check_email_fallback and new_status == "queued":
        try:
            _maybe_check_email_fallback_sync(db, conv)
        except Exception:
            logger.exception("email_fallback_check_failed conversation_id=%s", conv.id)


def atomic_claim_conversation(
    db: Session,
    conversation_id: uuid.UUID,
    human_agent: models.HumanAgent,
) -> models.Conversation:
    """Atomically claim a queued conversation; raises 409 if already claimed."""
    from fastapi import HTTPException
    # Conditional UPDATE rather than read-then-write, so two claims cannot both win
    updated = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.status == "queued",
        )
        .update(
            {
                "status": "human",
                "assigned_human_agent_id": human_agent.id,
                "updated_at": datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    if not updated:
        conv = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv.status == "human":
            if conv.assigned_human_agent_id == human_agent.id:
                return conv
            raise HTTPException(status_code=409, detail="Conversation already claimed by another agent")
        if conv.status == "resolved":
            raise HTTPException(status_code=400, detail="Conversation is already resolved")
        raise HTTPException(status_code=409, detail=f"Conversation cannot be claimed from '{conv.status}' status")
    db.commit()
    conv = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    logger.info("conversation_claimed_atomic id=%s by=%s", conversation_id, human_agent.id)
    return conv  # type: ignore


def _maybe_check_email_fallback_sync(db: Session, conv: models.Conversation) -> None:
    """Fallback-email gate; called after a transition to queued."""
    from datetime import timedelta

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

    # Skip when a human assigned to this agent is currently online
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


# Difficulty-aware variants: the owner's easy/balanced/hard choice shapes both the prompt
# and the tool description; should_allow_handoff() enforces the choice server-side.
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

# Difficulty presets: owner-facing copy plus the prompt and tool text sent to the model
HANDOFF_DIFFICULTY_META = {
    "easy": {
        "label": "Easy — helpful handoff",
        "short": "Offer human quickly",
        "desc": "AI offers a human after one brief attempt or at the first hint of frustration.",
        "tool_desc": (
            "Transfer to a human support agent. Be generous — call this promptly if the user hints at wanting a person "
            "(e.g. 'human', 'agent', 'person', 'talk to someone'), shows frustration, or if the issue seems even slightly complex/emotional. "
            "After one short troubleshooting try, you may proactively offer and call this."
        ),
        "policy": (
            "## Human Handoff Policy — Mode: EASY (lenient)\n"
            "- Be proactive and generous. If the user mentions 'human', 'agent', 'person', 'talk to someone', or shows any frustration, offer a handoff promptly.\n"
            "- Try at most ONE brief troubleshooting step; if not instantly resolved, say: 'I can connect you with a teammate who can pick this up right away — would you like me to?' and if the user says yes (or hints yes), call transfer_to_human.\n"
            "- Do not make the user repeat themselves. One clear signal is enough.\n"
        ),
        "suppression_msg": "I can connect you with a teammate right away if you’d prefer — or I can keep trying here. What would you like?",
    },
    "balanced": {
        "label": "Balanced — thoughtful helper",
        "short": "Try first, then offer",
        "desc": "AI tries 1–2 helpful steps, asks a clarifying question, then offers human if still stuck.",
        "tool_desc": (
            "Transfer this conversation to a human support agent. "
            "Call this when the user explicitly asks to speak with a human, when you have tried one or two troubleshooting steps and the issue persists, "
            "or when the situation requires human judgment. Provide a brief reason."
        ),
        "policy": (
            "## Human Handoff Policy — Mode: BALANCED\n"
            "- First try 1–2 concise, knowledge-grounded troubleshooting steps and ask ONE targeted clarifying question.\n"
            "- Only then, if the user explicitly asks for a human ('talk to human', 'agent please', 'person') or you cannot resolve after trying, offer: "
            "'I can connect you with a teammate — would you like me to?' and call transfer_to_human on yes.\n"
            "- Don’t call on the very first user message unless the user explicitly demanded a human.\n"
        ),
        "suppression_msg": "Let me try one more targeted suggestion before I connect you — could you share a bit more detail about what you’ve already tried?",
    },
    "hard": {
        "label": "Hard — persistent resolver",
        "short": "Insist twice",
        "desc": "AI exhausts knowledge, asks 2–3 questions, and only hands off if the user insists twice.",
        "tool_desc": (
            "Transfer to a human support agent. ONLY call this if the user has insisted on a human at least twice in this conversation "
            "(e.g. 'talk to human' repeated after you offered to keep helping), or you have exhausted 2–3 troubleshooting steps with clarifying questions and the user still explicitly says 'yes, connect me' or 'I want a person'. "
            "Never call on first contact. Be a persistent, thorough resolver first."
        ),
        "policy": (
            "## Human Handoff Policy — Mode: HARD (strict, persistent)\n"
            "- You are a persistent resolver. Never call transfer_to_human on the first 2–3 exchanges.\n"
            "- Always try to resolve yourself: use the knowledge base, propose 2–3 concrete steps, and ask targeted clarifying questions one at a time.\n"
            "- Only even consider handoff after you have tried and the user explicitly insists a SECOND time ('yes connect me', 'I want a human', repeated 'agent'). The first 'human please' should be met with: "
            "'I understand — let me try one more specific fix first; if that doesn’t help I’ll connect you right away. Does that sound fair?' and then continue helping.\n"
            "- Ask for permission before handing off: 'Would you like me to connect you now, or should I try another solution?' Only on clear 'yes/human' repeat, call transfer_to_human.\n"
            "- Never hand off for general frustration without explicit human request repeated.\n"
        ),
        "suppression_msg": "I hear you — let me try one more focused fix before I bring in a teammate. Could you tell me what happens when you try ...? If that doesn’t solve it, I’ll connect you immediately.",
    },
}

VALID_HANDOFF_DIFFICULTIES = set(HANDOFF_DIFFICULTY_META.keys())
DEFAULT_HANDOFF_DIFFICULTY = "balanced"


def get_transfer_tool_for_difficulty(difficulty: str) -> dict:
    meta = HANDOFF_DIFFICULTY_META.get(difficulty, HANDOFF_DIFFICULTY_META[DEFAULT_HANDOFF_DIFFICULTY])
    # Deep copy with difficulty-specific description
    import copy
    tool = copy.deepcopy(TRANSFER_TO_HUMAN_TOOL)
    tool["function"]["description"] = meta["tool_desc"]
    return tool


def get_handoff_policy_for_difficulty(difficulty: str) -> str:
    meta = HANDOFF_DIFFICULTY_META.get(difficulty, HANDOFF_DIFFICULTY_META[DEFAULT_HANDOFF_DIFFICULTY])
    return meta["policy"]


def get_handoff_suppression_message(difficulty: str) -> str:
    meta = HANDOFF_DIFFICULTY_META.get(difficulty, HANDOFF_DIFFICULTY_META[DEFAULT_HANDOFF_DIFFICULTY])
    return meta["suppression_msg"]



_HUMAN_REQUEST_PHRASES = (
    "talk to human", "speak to human", "human please", "need a human", "want a human",
    "talk to a person", "speak to a person", "human agent", "real person", "real agent",
    "agent please", "connect me", "connect to human", "talk to someone", "speak to someone",
    "representative", "live agent", "human support", "transfer to human",
)

def _contains_human_request(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _HUMAN_REQUEST_PHRASES) or (
        ("human" in t or "person" in t or "agent" in t) and any(w in t for w in ("talk", "speak", "need", "want", "connect", "please", "insist"))
    )

def should_allow_handoff(
    db: Session,
    conversation: models.Conversation,
    difficulty: str,
    current_user_message: str,
) -> tuple[bool, str]:
    """
    Server-side gate mirroring the prompt policy, so hard mode really requires
    insistence. Returns (allow, reason).
    """
    difficulty = difficulty if difficulty in VALID_HANDOFF_DIFFICULTIES else DEFAULT_HANDOFF_DIFFICULTY
    if difficulty == "easy":
        return True, "easy"
    try:
        if not conversation.session_id:
            return (difficulty != "hard"), "no session"
        # User messages within this conversation's window, newest first
        rows = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.session_id == conversation.session_id,
                models.ChatMessage.created_at >= conversation.created_at,
                models.ChatMessage.role == "user",
            )
            .order_by(models.ChatMessage.created_at.desc())
            .limit(10)
            .all()
        )
        user_texts = [r.content for r in rows]
        # Include current message (not yet persisted)
        if current_user_message:
            user_texts.insert(0, current_user_message)
        explicit_count = sum(1 for txt in user_texts if _contains_human_request(txt))
        total_user_turns = len(user_texts)

        if difficulty == "balanced":
            # Balanced stays permissive; the prompt does the discouraging
            return True, f"balanced explicit={explicit_count} turns={total_user_turns}"
        elif difficulty == "hard":
            if explicit_count >= 2:
                return True, f"hard explicit {explicit_count} >=2"
            if total_user_turns >= 4 and explicit_count >= 1 and _contains_human_request(current_user_message or ""):
                return True, f"hard turns {total_user_turns} with explicit current"
            # Not enough insistence
            return False, f"hard suppress explicit={explicit_count} turns={total_user_turns}"
    except Exception as exc:
        logger.exception("should_allow_handoff_check_failed conversation_id=%s err=%s", conversation.id, exc)
        # Permissive for easy/balanced so a check failure can't block handoff forever
        return difficulty != "hard", "exception fallback"
    return True, "default"


def build_handoff_ack_message(agent_display_name: str) -> str:
    return (
        "I'm connecting you with a member of our team — hang tight! "
        "They'll be with you shortly. 🙌"
    )
