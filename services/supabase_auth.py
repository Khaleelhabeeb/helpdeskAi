import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from supabase import Client, create_client

from db.database import SessionLocal
from models import User

load_dotenv()

security = HTTPBearer()
_supabase: Optional[Client] = None


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


def upsert_local_user(db: Session, supabase_user_id: str, email: str) -> User:
    user = db.query(User).filter(User.supabase_user_id == supabase_user_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, supabase_user_id=supabase_user_id, user_type="free")
        db.add(user)
    else:
        user.email = email
        user.supabase_user_id = supabase_user_id
    db.commit()
    db.refresh(user)
    return user


def verify_supabase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        response = get_supabase_client().auth.get_user(token)
        supabase_user_id, email = _normalize_supabase_user(response)
        return upsert_local_user(db, supabase_user_id, email)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Supabase token verification failed") from exc
