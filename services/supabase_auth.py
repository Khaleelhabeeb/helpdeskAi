import base64
import json
import logging
import os
import time
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from supabase import Client, create_client

from db.database import SessionLocal
from models import User
from services import cache_keys
from services.redis_client import get_sync_redis

load_dotenv()

security = HTTPBearer()
_supabase: Optional[Client] = None
logger = logging.getLogger(__name__)


_AUTH_CACHE_TTL_SECONDS = int(os.getenv("AUTH_CACHE_TTL_SECONDS", "120"))


def get_supabase_client() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise HTTPException(status_code=500, detail="Supabase auth is not configured")
        _supabase = create_client(url, key)
    return _supabase


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _read_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _normalize_supabase_user(response: Any) -> tuple[str, str]:
    user = _read_attr(response, "user", response)
    supabase_user_id = _read_attr(user, "id")
    email = _read_attr(user, "email")
    if not supabase_user_id or not email:
        raise HTTPException(status_code=401, detail="Invalid Supabase token")
    return str(supabase_user_id), str(email).lower()


def _token_cache_key(token: str) -> str:
    return cache_keys.auth_token(token)


def _token_expiry(token: str) -> Optional[int]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        exp = json.loads(decoded).get("exp")
        return int(exp) if exp else None
    except Exception:
        return None


def _get_cached_user(db: Session, token: str) -> Optional[User]:
    key = _token_cache_key(token)
    redis = get_sync_redis()
    if redis is None:
        return None
    try:
        user_id = redis.get(key)
    except Exception:
        logger.warning("auth_cache_read_failed", exc_info=True)
        return None
    if not user_id:
        return None
    try:
        user = db.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if user:
        return user
    try:
        redis.delete(key)
    except Exception:
        logger.warning("auth_cache_delete_failed", exc_info=True)
    return None


def _cache_user(token: str, user: User) -> None:
    token_exp = _token_expiry(token)
    now = time.time()
    expires_at = now + _AUTH_CACHE_TTL_SECONDS
    if token_exp:
        expires_at = min(expires_at, float(token_exp))
    if expires_at <= now:
        return

    key = _token_cache_key(token)
    redis = get_sync_redis()
    if redis is None:
        return
    try:
        redis.setex(key, max(1, int(expires_at - now)), str(user.id))
    except Exception:
        logger.warning("auth_cache_write_failed", exc_info=True)


def upsert_local_user(db: Session, supabase_user_id: str, email: str) -> User:
    user = db.query(User).filter(User.supabase_user_id == supabase_user_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
    changed = False
    if not user:
        user = User(email=email, supabase_user_id=supabase_user_id, user_type="free", credits_remaining=999999)
        db.add(user)
        changed = True
    else:
        if user.email != email:
            user.email = email
            changed = True
        if user.supabase_user_id != supabase_user_id:
            user.supabase_user_id = supabase_user_id
            changed = True

    if changed:
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.supabase_user_id == supabase_user_id).first()
            if not user:
                user = db.query(User).filter(User.email == email).first()
            if not user:
                logger.exception("Failed to upsert local user after integrity conflict")
                raise
    return user


def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    cached_user = _get_cached_user(db, token)
    if cached_user:
        return cached_user

    try:
        response = get_supabase_client().auth.get_user(token)
        supabase_user_id, email = _normalize_supabase_user(response)
        user = upsert_local_user(db, supabase_user_id, email)
        _cache_user(token, user)
        return user
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Supabase token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.") from exc
