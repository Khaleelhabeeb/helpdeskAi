from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import requests
from datetime import timedelta
from db.database import SessionLocal
from db import models, schemas
from utils.security import hash_password, verify_password
from utils.jwt import create_access_token, verify_token, get_current_user
from dotenv import load_dotenv
from datetime import datetime

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

load_dotenv()
security = HTTPBearer()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

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
    if db.query(models.User).filter(models.User.email == normalized_email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = models.User(
        email=normalized_email,
        hashed_password=hash_password(user.password),
        user_type="free"  # Explicitly setting new users to free tier
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully"}

@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, user: schemas.UserLogin, db: Session = Depends(get_db)):
    normalized_email = user.email.lower()
    db_user = db.query(models.User).filter(models.User.email == normalized_email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": db_user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_type": db_user.user_type
    } 

@router.get("/google")
@limiter.limit("10/minute")
def google_auth(request: Request, code: str, db: Session = Depends(get_db)):
    """
    Endpoint to handle Google OAuth callback.
    It exchanges the provided authorization code for tokens and returns a JWT access token.
    """
    token_endpoint = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": "http://127.0.0.1:8000/auth/google/callback",
        "grant_type": "authorization_code"
    }
    token_response = requests.post(token_endpoint, data=data)
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch tokens from Google")

    token_json = token_response.json()
    id_token = token_json.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token received from Google")

    from jose import jwt
    try:
        user_info = jwt.get_unverified_claims(id_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to decode id_token")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email found in token")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        new_user = models.User(
        email=email,
        hashed_password=hash_password("google_oauth_user"),
        user_type="free"  # Set Google OAuth users to free by default
    )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user = new_user

    token = create_access_token({"sub": user.email}, expires_delta=timedelta(days=7))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_type": user.user_type
    }

@router.get("/google/callback")
@limiter.limit("10/minute")
def google_callback(request: Request, code: str, db: Session = Depends(get_db)):
    """
    Callback endpoint for Google OAuth.
    Exchanges the provided authorization code for tokens,
    then redirects to the front end with the token and user email.
    """
    token_endpoint = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,  # <-- UPDATED
        "grant_type": "authorization_code"
    }
    token_response = requests.post(token_endpoint, data=data)
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch tokens from Google")
    token_json = token_response.json()
    id_token = token_json.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token received from Google")
    from jose import jwt
    try:
        # For production, validate the token signature properly.
        user_info = jwt.get_unverified_claims(id_token)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to decode id_token")
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email found in token")
    # Look up the user; create if needed.
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        new_user = models.User(
            email=email,
            hashed_password=hash_password("google_oauth_user"),
            user_type="free"  # Set Google OAuth users to free by default
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user = new_user
    access_token = create_access_token({"sub": user.email}, expires_delta=timedelta(days=7))
    # Redirect to the production frontend, now including user_type in the query params
    redirect_url = f"https://example.web.app/auth?token={access_token}&email={user.email}&user_type={user.user_type}"
    return RedirectResponse(redirect_url)

@router.get("/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifies if the provided JWT token is valid.
    Returns 200 OK if valid, 401 Unauthorized if invalid.
    """
    try:
        token = credentials.credentials
        verify_token(token)
        return {"status": "valid"}
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/upgrade/{tier}")
def upgrade_user(
    tier: str,
    db: Session = Depends(get_db), 
    user = Depends(get_current_user)
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