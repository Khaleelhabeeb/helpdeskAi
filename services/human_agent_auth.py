"""Human-agent auth helpers.

Human agents are not Supabase users: they have their own bcrypt password hash and a
role=human_agent JWT, so the permission boundary is enforced at the token level.
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

def _get_jwt_secret() -> str:
    sec = (os.getenv("JWT_SECRET") or os.getenv("WIDGET_SECRET") or "").strip()
    if not sec or sec == "dev-secret-change-me":
        if os.getenv("ENV") == "production":
            raise RuntimeError("JWT_SECRET must be set in production")
        sec = "dev-secret-change-me"
    return sec

JWT_SECRET = _get_jwt_secret()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "helpdeskai")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "human_agent")
# 12h default; raise HUMAN_AGENT_JWT_TTL_HOURS if longer sessions are needed
HUMAN_AGENT_JWT_TTL_HOURS = int(os.getenv("HUMAN_AGENT_JWT_TTL_HOURS", "12"))
INVITE_TOKEN_TTL_DAYS = int(os.getenv("INVITE_TOKEN_TTL_DAYS", "7"))
# Compared against when a user has no hash, so failed logins take the same time
_DUMMY_BCRYPT_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode("utf-8")



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



def hash_invite_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def create_invite_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=INVITE_TOKEN_TTL_DAYS)
    return token, expires


def find_human_by_invite_token(db: Session, raw_token: str) -> Optional[models.HumanAgent]:
    """
    Lookup human agent by invite token, supporting both hashed (new) and plaintext (legacy) rows.
    Tries hashed lookup first, then falls back to raw equality for migration.
    """
    raw = raw_token.strip()
    hashed = hash_invite_token(raw)
    ha = db.query(models.HumanAgent).filter(models.HumanAgent.invite_token == hashed).first()
    if ha:
        return ha
    # Fallback for legacy plaintext rows (pre-migration)
    ha2 = db.query(models.HumanAgent).filter(models.HumanAgent.invite_token == raw).first()
    return ha2



def create_human_agent_jwt(human_agent: models.HumanAgent) -> str:
    # Re-read secret to respect ENV changes
    secret = _get_jwt_secret()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=HUMAN_AGENT_JWT_TTL_HOURS)
    payload = {
        "sub": str(human_agent.id),
        "human_agent_id": str(human_agent.id),
        "owner_user_id": int(human_agent.owner_user_id),
        "email": human_agent.email,
        "role": "human_agent",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def create_ws_ticket(human_agent: models.HumanAgent, ttl_seconds: int = 60) -> str:
    """Create a short-lived single-use WS ticket (60s) to avoid JWT in query string."""
    secret = _get_jwt_secret()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": str(human_agent.id),
        "human_agent_id": str(human_agent.id),
        "owner_user_id": int(human_agent.owner_user_id),
        "role": "human_agent",
        "iss": JWT_ISSUER,
        "aud": "human_agent_ws",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_human_agent_jwt(token: str, *, audience: str | None = None) -> dict:
    secret = _get_jwt_secret()
    aud = audience or JWT_AUDIENCE
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER, audience=aud)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Human agent session expired. Please sign in again.") from exc
    except jwt.InvalidTokenError:
        # Legacy tokens (no iss/aud) only when explicitly allowed for migration
        if os.getenv("ALLOW_LEGACY_HUMAN_JWT", "0") == "1":
            try:
                return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"verify_aud": False, "verify_iss": False})
            except jwt.ExpiredSignatureError as exc:
                raise HTTPException(status_code=401, detail="Human agent session expired. Please sign in again.") from exc
            except jwt.InvalidTokenError as exc:
                raise HTTPException(status_code=401, detail="Invalid human agent token.") from exc
        raise HTTPException(status_code=401, detail="Invalid human agent token.")


def verify_password_with_dummy(plain: str, hashed: str | None) -> bool:
    """Constant-time wrapper: always runs a bcrypt compare, even without a stored hash."""
    if not hashed:
        try:
            bcrypt.checkpw(plain.encode("utf-8"), _DUMMY_BCRYPT_HASH.encode("utf-8"))
        except Exception:
            pass
        return False
    return verify_password(plain, hashed)



def resolve_human_agent_for_email(
    db: Session, email: str, selected_id: str | None = None
) -> models.HumanAgent:
    """Resolve the caller's agent membership from a verified (Supabase) email.

    One login carries every role: the email proves ownership of each membership.
    Zero rows → 404 (no agent membership); several → the caller must pick one via
    `selected_id` (X-Human-Agent-ID), else 409.
    """
    rows = (
        db.query(models.HumanAgent)
        .filter(models.HumanAgent.email == email.lower().strip())
        .filter(models.HumanAgent.status == "active")
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="This sign-in has no human-agent workspace. Ask the account owner for an invite.",
        )
    if selected_id:
        try:
            sel = uuid.UUID(str(selected_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid workspace selection")
        for ha in rows:
            if ha.id == sel:
                return ha
        raise HTTPException(status_code=403, detail="Selected workspace is not one of your memberships")
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This sign-in belongs to several agent workspaces. Select one.",
                "memberships": [
                    {"human_agent_id": str(ha.id), "owner_user_id": ha.owner_user_id, "name": ha.name}
                    for ha in rows
                ],
            },
        )
    return rows[0]


def get_current_human_agent(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> models.HumanAgent:
    # Legacy path first: dedicated human-agent JWT (grandfathered until migration).
    if credentials and credentials.credentials:
        try:
            payload = decode_human_agent_jwt(credentials.credentials)
        except HTTPException:
            payload = None
        if payload is not None and payload.get("role") == "human_agent":
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
        # A non-legacy Bearer token may be a Supabase session — fall through.
    # Unified path: the same Supabase login owners use. Email proves membership.
    auth = request.headers.get("authorization") if request is not None else None
    token: str | None = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing human agent authentication")
    try:
        from services.supabase_auth import verify_supabase_token_string
        user = verify_supabase_token_string(token, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Missing human agent authentication")
    selected = request.headers.get("x-human-agent-id") if request is not None else None
    return resolve_human_agent_for_email(db, user.email, selected)


def resolve_ws_human_agent(
    db: Session, token: str, requested_id: str | None = None
) -> models.HumanAgent | None:
    """WebSocket handshake auth: legacy JWT / ws_ticket first, Supabase session second."""
    for aud in ("human_agent_ws", "human_agent"):
        try:
            payload = decode_human_agent_jwt(token, audience=aud)
            break
        except HTTPException:
            payload = None
    if payload is None:
        try:
            payload = decode_human_agent_jwt(token)  # legacy fallback
        except HTTPException:
            payload = None
    if payload is not None and payload.get("role") == "human_agent":
        try:
            ha_uuid = uuid.UUID(str(payload.get("human_agent_id") or payload.get("sub")))
        except Exception:
            return None
        ha = db.query(models.HumanAgent).filter(models.HumanAgent.id == ha_uuid).first()
        return ha if ha and ha.status == "active" else None
    # Unified path: Supabase access token, membership resolved by verified email.
    # A 409 (several workspaces, no selection) propagates so the socket can use
    # a distinct close code instead of looking like an auth failure.
    try:
        from services.supabase_auth import verify_supabase_token_string
        user = verify_supabase_token_string(token, db)
        return resolve_human_agent_for_email(db, user.email, requested_id)
    except HTTPException as exc:
        if exc.status_code == 409:
            raise
        return None


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
