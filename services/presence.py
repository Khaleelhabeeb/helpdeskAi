"""In-process human-agent presence: an open-dashboard-WebSocket count per agent.

Derived from the number of live dashboard connections this process holds, so it is
per-worker and does not survive a restart.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Set
import uuid

from sqlalchemy.orm import Session
from db import models

logger = logging.getLogger(__name__)

# human_agent_id (str) → active WebSocket connection count
_presence_counts: Dict[str, int] = defaultdict(int)
# human_agent_id (str) → last_seen, used by the TTL check
_presence_last_seen: Dict[str, datetime] = {}
_lock = asyncio.Lock()


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


async def human_agent_heartbeat(human_agent_id: str) -> None:
    async with _lock:
        _presence_last_seen[human_agent_id] = datetime.now(timezone.utc)


PRESENCE_TTL_SECONDS = int(os.getenv("PRESENCE_TTL_SECONDS", "120"))  # covers crashed workers

def _is_presence_fresh(human_agent_id: str) -> bool:
    cnt = _presence_counts.get(human_agent_id, 0)
    if cnt <= 0:
        return False
    last = _presence_last_seen.get(human_agent_id)
    if last is None:
        return True
    try:
        age = (datetime.now(timezone.utc) - (last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last)).total_seconds()
        if age > PRESENCE_TTL_SECONDS:
            # Treat as offline and clean up lazily
            _presence_counts.pop(human_agent_id, None)
            return False
    except Exception:
        pass
    return True

def is_human_agent_online_sync(human_agent_id: str) -> bool:
    return _is_presence_fresh(human_agent_id)


async def is_human_agent_online(human_agent_id: str) -> bool:
    async with _lock:
        return _is_presence_fresh(human_agent_id)


def is_any_human_online_for_agent_sync(db: Session, agent_id: uuid.UUID) -> bool:
    """True if any human agent assigned to `agent_id` is online (TTL-aware)."""
    rows = db.query(models.AgentAssignment).filter(models.AgentAssignment.agent_id == agent_id).all()
    if not rows:
        return False
    for row in rows:
        if _is_presence_fresh(str(row.human_agent_id)):
            return True
    return False


async def is_any_human_online_for_agent(db: Session, agent_id: uuid.UUID) -> bool:
    return is_any_human_online_for_agent_sync(db, agent_id)


def get_online_human_agent_ids() -> Set[str]:
    return {k for k, v in _presence_counts.items() if v > 0}


def get_presence_snapshot() -> Dict[str, int]:
    return dict(_presence_counts)


def _clear_for_tests() -> None:
    _presence_counts.clear()
    _presence_last_seen.clear()
