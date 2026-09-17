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
    # Accept both legacy tokens (no iss/aud) and current ones: try strict first, then lenient
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER, audience=aud)
    except jwt.InvalidTokenError:
        # Fallback for legacy tokens missing iss/aud: decode without verification of iss/aud
        try:
            return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], options={"verify_aud": False, "verify_iss": False})
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status_code=401, detail="Human agent session expired. Please sign in again.") from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail="Invalid human agent token.") from exc
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Human agent session expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid human agent token.") from exc


def verify_password_with_dummy(plain: str, hashed: str | None) -> bool:
    """Constant-time wrapper: always runs a bcrypt compare, even without a stored hash."""
    if not hashed:
        try:
            bcrypt.checkpw(plain.encode("utf-8"), _DUMMY_BCRYPT_HASH.encode("utf-8"))
        except Exception:
            pass
        return False
    return verify_password(plain, hashed)



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
