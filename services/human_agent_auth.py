"""
Human-agent auth helpers (§2).

Human agents are NOT Supabase users — they have their own password hash
(bcrypt) and JWT (role=human_agent). This keeps the permission boundary
enforced at the token level so a bug in query filtering can't leak
cross-account data.
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db import models
from services.supabase_auth import get_db  # re-use generator

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
HUMAN_AGENT_JWT_TTL_HOURS = int(os.getenv("HUMAN_AGENT_JWT_TTL_HOURS", "168"))  # 7 days
INVITE_TOKEN_TTL_DAYS = int(os.getenv("INVITE_TOKEN_TTL_DAYS", "7"))


# ── Password helpers (bcrypt) ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    # bcrypt hash is bytes; store as utf-8 string
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Invite token ─────────────────────────────────────────────────────────────

def create_invite_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=INVITE_TOKEN_TTL_DAYS)
    return token, expires


# ── JWT ──────────────────────────────────────────────────────────────────────

def create_human_agent_jwt(human_agent: models.HumanAgent) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=HUMAN_AGENT_JWT_TTL_HOURS)
    payload = {
        "sub": str(human_agent.id),
        "human_agent_id": str(human_agent.id),
        "owner_user_id": int(human_agent.owner_user_id),
        "email": human_agent.email,
        "role": "human_agent",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_human_agent_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Human agent session expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid human agent token.") from exc


# ── FastAPI dependency ───────────────────────────────────────────────────────

def get_current_human_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> models.HumanAgent:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing human agent authentication")
    payload = decode_human_agent_jwt(credentials.credentials)
    if payload.get("role") != "human_agent":
        raise HTTPException(status_code=403, detail="Not a human agent token")
    human_agent_id = payload.get("human_agent_id") or payload.get("sub")
    if not human_agent_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    try:
        ha_uuid = uuid.UUID(str(human_agent_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid human agent id in token")

    ha = db.query(models.HumanAgent).filter(models.HumanAgent.id == ha_uuid).first()
    if not ha:
        raise HTTPException(status_code=401, detail="Human agent not found")
    if ha.status != "active":
        raise HTTPException(status_code=403, detail=f"Human agent is {ha.status}")
    # also ensure owner_user_id matches token (tamper check)
    owner_in_token = payload.get("owner_user_id")
    if owner_in_token is not None and int(ha.owner_user_id) != int(owner_in_token):
        raise HTTPException(status_code=401, detail="Token owner mismatch")
    return ha


def get_current_human_agent_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[models.HumanAgent]:
    """Try to resolve human agent from Authorization header, return None if not present/invalid (for WS handshake with query token)."""
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    token: Optional[str] = None
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    # Also accept token via query param `token` for WebSocket
    if not token:
        token = request.query_params.get("token")
    if not token:
        return None
    try:
        payload = decode_human_agent_jwt(token)
    except HTTPException:
        return None
    if payload.get("role") != "human_agent":
        return None
    try:
        ha_uuid = uuid.UUID(str(payload.get("human_agent_id") or payload.get("sub")))
    except Exception:
        return None
    ha = db.query(models.HumanAgent).filter(models.HumanAgent.id == ha_uuid).first()
    if not ha or ha.status != "active":
        return None
    return ha
