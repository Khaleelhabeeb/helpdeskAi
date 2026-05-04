from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
import os
from datetime import timedelta
from db.database import SessionLocal
from db import schemas
from db import models
from services.supabase_auth import get_supabase_client, upsert_local_user, verify_supabase_token
from dotenv import load_dotenv
from datetime import datetime

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

load_dotenv()


@router.get("/supabase-config")
def supabase_config():
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise HTTPException(status_code=500, detail="Supabase config is missing")
    return {"url": url, "anon_key": anon_key}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

@router.post("/upgrade/{tier}")
def upgrade_user(
    tier: str,
    db: Session = Depends(get_db), 
    user = Depends(verify_supabase_token)
):
    """
    Upgrades a user to the specified tier.
    Tier can be 'free', 'paid', or 'pro'.
    In a production, integrate with a payment processor here.
    """
    if tier not in ["free", "paid", "pro"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'free', 'paid', or 'pro'")
    
    db_user = db.query(models.User).filter(models.User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Set the tier
    db_user.user_type = tier

    # Reset credits based on the new tier
    if tier == "free":
        db_user.credits_remaining = 100
    elif tier == "paid":
        db_user.credits_remaining = 2000
    elif tier == "pro":
        db_user.credits_remaining = 20000

    # Update reset date
    db_user.last_reset_date = datetime.utcnow()

    db.commit()
    db.refresh(db_user)
    
    return {
        "message": f"User upgraded to {tier} tier successfully", 
        "user_type": db_user.user_type,
        "credits_remaining": db_user.credits_remaining,
        "next_reset": db_user.last_reset_date + timedelta(days=30)
    }
