from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import os
from datetime import timedelta
from db import schemas
from db import models
from services.supabase_auth import get_db, get_supabase_client, upsert_local_user, verify_supabase_token
from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

load_dotenv()


class OAuthCodeExchange(BaseModel):
    code: str
    code_verifier: str
    redirect_to: str | None = None


@router.get("/supabase-config")
def supabase_config():
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise HTTPException(status_code=500, detail="Supabase config is missing")
    return {"url": url, "anon_key": anon_key}

@router.post("/signup")
@limiter.limit("5/minute")
def signup(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    normalized_email = user.email.lower()
    try:
        response = get_supabase_client().auth.sign_up(
            {"email": normalized_email, "password": user.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    supabase_user = getattr(response, "user", None)
    if supabase_user:
        upsert_local_user(db, str(supabase_user.id), normalized_email)

    session = getattr(response, "session", None)
    return {
        "message": "User created successfully",
        "access_token": getattr(session, "access_token", None),
        "refresh_token": getattr(session, "refresh_token", None),
        "token_type": "bearer",
    }

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, user: schemas.UserLogin, db: Session = Depends(get_db)):
    normalized_email = user.email.lower()
    try:
        response = get_supabase_client().auth.sign_in_with_password(
            {"email": normalized_email, "password": user.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid credentials") from exc

    supabase_user = getattr(response, "user", None)
    if not supabase_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    db_user = upsert_local_user(db, str(supabase_user.id), normalized_email)
    session = getattr(response, "session", None)
    return {
        "access_token": getattr(session, "access_token", None),
        "refresh_token": getattr(session, "refresh_token", None),
        "token_type": "bearer",
        "user_type": db_user.user_type
    } 


@router.get("/google/callback")
@limiter.limit("10/minute")
def google_callback(request: Request, code: str, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=410,
        detail="Google OAuth callback moved to Supabase Auth. Configure Google in Supabase and use the Supabase callback flow.",
    )

@router.get("/verify")
def verify_auth(user = Depends(verify_supabase_token)):
    return {"status": "valid", "user_id": user.id, "email": user.email}


@router.post("/oauth/exchange")
def exchange_oauth_code(payload: OAuthCodeExchange, db: Session = Depends(get_db)):
    try:
        response = get_supabase_client().auth.exchange_code_for_session(
            {
                "auth_code": payload.code,
                "code_verifier": payload.code_verifier,
                "redirect_to": payload.redirect_to,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Could not finish Google sign-in") from exc

    supabase_user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if not supabase_user and session:
        supabase_user = getattr(session, "user", None)
    if not supabase_user:
        raise HTTPException(status_code=401, detail="Could not finish Google sign-in")

    db_user = upsert_local_user(db, str(supabase_user.id), str(supabase_user.email).lower())
    return {
        "access_token": getattr(session, "access_token", None),
        "refresh_token": getattr(session, "refresh_token", None),
        "token_type": "bearer",
        "user_type": db_user.user_type,
    }

@router.post("/upgrade/{tier}")
def upgrade_user(
    tier: str,
    db: Session = Depends(get_db), 
    user = Depends(verify_supabase_token)
):
    db_user = db.query(models.User).filter(models.User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.user_type = "free"
    db_user.credits_remaining = 999999

    # Update reset date
    db_user.last_reset_date = datetime.utcnow()

    db.commit()
    db.refresh(db_user)
    
    return {
        "message": "Plans are currently disabled; your workspace has full access.", 
        "user_type": db_user.user_type,
        "credits_remaining": db_user.credits_remaining,
        "next_reset": db_user.last_reset_date + timedelta(days=30)
    }
