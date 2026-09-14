"""
Human-agent presence tracking (§4, §5).

Presence is defined as: does this human agent currently have a dashboard
WebSocket open?  Tracked in-memory per process (no DB, no Redis) for v1.
A simple connection counter per human_agent_id is sufficient.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Set
import uuid

from sqlalchemy.orm import Session
from db import models

logger = logging.getLogger(__name__)

# ── In-process state ─────────────────────────────────────────────────────────
# human_agent_id (str) → active WebSocket connection count
_presence_counts: Dict[str, int] = defaultdict(int)
# human_agent_id (str) → last_seen timestamp (for debugging / future expiry)
_presence_last_seen: Dict[str, datetime] = {}
_lock = asyncio.Lock()

# Also a quick index: agent_id (str) → set of human_agent_ids that are online
# rebuilt lazily via is_any_human_online_for_agent which queries DB + checks _presence_counts


async def human_agent_connected(human_agent_id: str) -> None:
    async with _lock:
        _presence_counts[human_agent_id] += 1
        _presence_last_seen[human_agent_id] = datetime.now(timezone.utc)
    logger.info("presence_connected human_agent_id=%s count=%s", human_agent_id, _presence_counts[human_agent_id])


async def human_agent_disconnected(human_agent_id: str) -> None:
    async with _lock:
        cur = _presence_counts.get(human_agent_id, 0)
        if cur <= 1:
            _presence_counts.pop(human_agent_id, None)
        else:
            _presence_counts[human_agent_id] = cur - 1
        _presence_last_seen[human_agent_id] = datetime.now(timezone.utc)
    logger.info("presence_disconnected human_agent_id=%s remaining=%s", human_agent_id, _presence_counts.get(human_agent_id, 0))


def is_human_agent_online_sync(human_agent_id: str) -> bool:
    """Sync check (callable from non-async contexts)."""
    return _presence_counts.get(human_agent_id, 0) > 0


async def is_human_agent_online(human_agent_id: str) -> bool:
    async with _lock:
        return _presence_counts.get(human_agent_id, 0) > 0


def is_any_human_online_for_agent_sync(db: Session, agent_id: uuid.UUID) -> bool:
    """
    Return True if at least one human agent assigned to `agent_id` is currently online.

    This is the gate used in §5 email fallback:
      - If no human is online at the moment of `queued` transition, send fallback email.
    """
    # Find all human agents assigned to this AI agent
    rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.agent_id == agent_id).all()
    if not rows:
        return False
    # Check if any of those human agents has an active WS
    for row in rows:
        if _presence_counts.get(str(row.human_agent_id), 0) > 0:
            return True
    return False


async def is_any_human_online_for_agent(db: Session, agent_id: uuid.UUID) -> bool:
    # DB query is sync; run in thread if needed — but caller is usually async
    # For now just call sync version (SQLAlchemy session is sync anyway)
    return is_any_human_online_for_agent_sync(db, agent_id)


def get_online_human_agent_ids() -> Set[str]:
    return {k for k, v in _presence_counts.items() if v > 0}


def get_presence_snapshot() -> Dict[str, int]:
    return dict(_presence_counts)


def _clear_for_tests() -> None:
    _presence_counts.clear()
    _presence_last_seen.clear()
