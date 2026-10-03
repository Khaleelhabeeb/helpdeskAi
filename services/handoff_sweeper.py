"""Background sweeper: auto-close idle handoffs, requeue abandoned claims.

Runs every 60s from main.py lifespan with a Postgres advisory lock so N
replicas never double-close. Each pass is a bounded batch (200) using
SELECT ... FOR UPDATE SKIP LOCKED semantics via ordered queries + atomic
per-row transitions.

Timeouts (env-overridable):
  HANDOFF_VISITOR_IDLE_CLOSE_S=900      human + no visitor msg → resolved(visitor_idle)
  HANDOFF_AGENT_IDLE_REQUEUE_S=300      human + assignee offline/idle → queued
  HANDOFF_QUEUED_MAX_WAIT_S=1800        queued too long → resolved(queue_timeout)
  HANDOFF_COLLECTING_EMAIL_EXPIRE_S=86400 collecting_email stale → resolved(email_timeout)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_S = int(os.getenv("HANDOFF_SWEEP_INTERVAL_S", "60"))
SWEEP_BATCH = int(os.getenv("HANDOFF_SWEEP_BATCH", "200"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _try_advisory_lock(db) -> bool:
    """Single-flight across replicas (session-level lock, held until released).

    Must NOT use pg_try_advisory_xact_lock: xact locks release on the first
    COMMIT, and the sweep commits per row — replicas would double-close.
    """
    try:
        from sqlalchemy import text as _text
        row = db.execute(_text("SELECT pg_try_advisory_lock(727271001)")).first()
        return bool(row and row[0])
    except Exception:
        # SQLite / tests: no advisory locks — allow sweep
        return True


def _release_advisory_lock(db) -> None:
    try:
        from sqlalchemy import text as _text
        db.execute(_text("SELECT pg_advisory_unlock(727271001)"))
    except Exception:
        pass


def _is_assignee_online(db, assignee_id) -> bool:
    if not assignee_id:
        return False
    try:
        from services.presence import is_human_agent_online_sync, PRESENCE_TTL_SECONDS
        if is_human_agent_online_sync(str(assignee_id)):
            return True
    except Exception:
        pass
    # DB presence fallback
    try:
        from db import models
        row = db.query(models.HumanPresence).filter(
            models.HumanPresence.human_agent_id == assignee_id
        ).first()
        if not row:
            return False
        last = _as_aware(row.last_heartbeat_at)
        if not last:
            return False
        ttl = int(os.getenv("PRESENCE_TTL_SECONDS", "120"))
        return (_now() - last).total_seconds() <= ttl and (row.connection_count or 0) > 0
    except Exception:
        return False


def sweep_once() -> dict:
    """Run one sweep pass. Returns counts per action. Safe to call from any thread."""
    from db.database import BackgroundSession
    from db import models
    from services.handoff_service import (
        AGENT_IDLE_REQUEUE_S,
        COLLECTING_EMAIL_EXPIRE_S,
        QUEUED_MAX_WAIT_S,
        VISITOR_IDLE_CLOSE_S,
        transition_status,
    )

    stats = {"visitor_idle_closed": 0, "agent_requeued": 0, "queue_timeout": 0, "email_expired": 0}
    db = BackgroundSession()
    lock_held = False
    try:
        now = _now()
        # Advisory lock (postgres only)
        try:
            if not _try_advisory_lock(db):
                return stats
            lock_held = True
        except Exception:
            pass

        def _stale(conv, ts, secs: int) -> bool:
            t = _as_aware(ts) or _as_aware(getattr(conv, "updated_at", None))
            return bool(t and (now - t).total_seconds() >= secs)

        # 1. human + visitor idle → resolved(visitor_idle)
        rows = (
            db.query(models.Conversation)
            .filter(models.Conversation.status == "human")
            .order_by(models.Conversation.updated_at.asc())
            .limit(SWEEP_BATCH)
            .all()
        )
        for conv in rows:
            try:
                visitor_ts = getattr(conv, "last_visitor_at", None) or conv.updated_at
                agent_ts = getattr(conv, "last_agent_at", None) or conv.updated_at
                # Visitor idle close
                if _stale(conv, visitor_ts, VISITOR_IDLE_CLOSE_S):
                    transition_status(db, conv, "resolved", force=True, close_reason="visitor_idle")
                    try:
                        db.add(models.ChatMessage(
                            session_id=conv.session_id, role="assistant",
                            content="Closing this chat due to inactivity. Reply anytime to start a new conversation.",
                            sender_type="system", created_at=now,
                        ))
                        db.commit()
                    except Exception:
                        db.rollback()
                    stats["visitor_idle_closed"] += 1
                    continue
                # Agent abandon → requeue (assignee offline or no agent activity)
                if _stale(conv, agent_ts, AGENT_IDLE_REQUEUE_S) and not _is_assignee_online(db, conv.assigned_human_agent_id):
                    transition_status(db, conv, "queued", force=True)
                    try:
                        if conv.session_id:
                            db.add(models.ChatMessage(
                                session_id=conv.session_id, role="assistant",
                                content="Your agent disconnected — you're back in the queue; the next available teammate will pick this up.",
                                sender_type="system", created_at=now,
                            ))
                            db.commit()
                    except Exception:
                        db.rollback()
                    stats["agent_requeued"] += 1
            except Exception:
                logger.exception("sweep_human_failed id=%s", getattr(conv, "id", "?"))
                try:
                    db.rollback()
                except Exception:
                    pass

        # 2. queued too long → resolved(queue_timeout) + fallback email attempt
        qrows = (
            db.query(models.Conversation)
            .filter(models.Conversation.status == "queued")
            .order_by(models.Conversation.updated_at.asc())
            .limit(SWEEP_BATCH)
            .all()
        )
        for conv in qrows:
            try:
                queued_ts = getattr(conv, "queued_at", None) or conv.updated_at
                if _stale(conv, queued_ts, QUEUED_MAX_WAIT_S):
                    from services.handoff_service import _maybe_check_email_fallback_sync
                    try:
                        _maybe_check_email_fallback_sync(db, conv)
                    except Exception:
                        pass
                    transition_status(db, conv, "resolved", force=True, close_reason="queue_timeout")
                    stats["queue_timeout"] += 1
            except Exception:
                logger.exception("sweep_queued_failed id=%s", getattr(conv, "id", "?"))
                try:
                    db.rollback()
                except Exception:
                    pass

        # 3. collecting_email stale → resolved(email_timeout)
        erows = (
            db.query(models.Conversation)
            .filter(models.Conversation.status == "collecting_email")
            .order_by(models.Conversation.updated_at.asc())
            .limit(SWEEP_BATCH)
            .all()
        )
        for conv in erows:
            try:
                if _stale(conv, conv.updated_at, COLLECTING_EMAIL_EXPIRE_S):
                    transition_status(db, conv, "resolved", force=True, close_reason="email_timeout")
                    stats["email_expired"] += 1
            except Exception:
                logger.exception("sweep_email_failed id=%s", getattr(conv, "id", "?"))
                try:
                    db.rollback()
                except Exception:
                    pass

        if any(stats.values()):
            logger.info("handoff_sweep done=%s", stats)
        return stats
    finally:
        try:
            if lock_held:
                _release_advisory_lock(db)
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass


async def sweeper_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(sweep_once)
        except Exception:
            logger.exception("handoff_sweep_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=SWEEP_INTERVAL_S)
        except asyncio.TimeoutError:
            pass
