from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.orm import Session
import os
from datetime import timedelta
from db import schemas
from db import models
from services.supabase_auth import get_db, get_supabase_client, upsert_local_user, verify_supabase_token
from dotenv import load_dotenv
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr
from utils.rate_limit import create_limiter

limiter = create_limiter()
router = APIRouter()

load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL")


class OAuthCodeExchange(BaseModel):
    code: str
    code_verifier: str
    redirect_to: str | None = None


class RefreshTokenPayload(BaseModel):
    refresh_token: str


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    token: str
    type: str | None = "email"


def _read_attr(obj, name: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _extract_session_data(response):
    session = _read_attr(response, "session", response)
    access_token = _read_attr(session, "access_token")
    refresh_token = _read_attr(session, "refresh_token")
    return access_token, refresh_token


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    status_code = _read_attr(exc, "status_code")
    code = _read_attr(exc, "code")
    return (
        status_code == 429
        or code == 429
        or "too many requests" in message
        or "rate limit" in message
        or "429" in message
    )


@router.get("/supabase-config")
def supabase_config():
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise HTTPException(status_code=500, detail="Supabase config is missing")
    return {"url": url, "anon_key": anon_key}


# Magic-link only: Supabase's ConfirmationURL is used (not the 6-digit OTP), so the email
# template must contain {{ .ConfirmationURL }}; verification happens when Supabase
# redirects to FRONTEND_URL/auth/callback.

_otp_email_buckets: dict[str, list[float]] = {}
import time as _time
import threading as _threading
_otp_lock = _threading.Lock()
# Anti email-bombing caps (per email per hour). Restart resets buckets.
_OTP_REQUEST_PER_HOUR = 10
_OTP_VERIFY_PER_HOUR = 10


# Best-effort single-process throttle (Redis would be needed for multi-worker).
_OTP_BUCKET_MAX_KEYS = 5000


def _otp_email_allowed(email: str, *, max_per_hour: int = 5) -> bool:
    now = _time.time()
    with _otp_lock:
        bucket = [t for t in _otp_email_buckets.get(email, []) if now - t < 3600]
        if len(bucket) >= max_per_hour:
            _otp_email_buckets[email] = bucket
            return False
        bucket.append(now)
        _otp_email_buckets[email] = bucket
        while len(_otp_email_buckets) > _OTP_BUCKET_MAX_KEYS:
            _otp_email_buckets.pop(next(iter(_otp_email_buckets)))
        return True


@router.post("/otp/request")
@limiter.limit("5/minute")
def request_otp(request: Request, response: Response, body: OtpRequest):
    """Send a magic link, creating the Supabase user if it does not exist. Always returns success."""
    normalized_email = body.email.lower().strip()
    if not _otp_email_allowed(normalized_email, max_per_hour=_OTP_REQUEST_PER_HOUR):
        raise HTTPException(status_code=429, detail="Too many email requests. Please wait and try again.")
    redirect_to = f"{FRONTEND_URL}/auth/callback" if FRONTEND_URL else None

    payload: dict = {"email": normalized_email}
    if redirect_to:
        payload["options"] = {"email_redirect_to": redirect_to, "should_create_user": True}
    else:
        payload["options"] = {"should_create_user": True}

    try:
        get_supabase_client().auth.sign_in_with_otp(payload)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            raise HTTPException(
                status_code=429,
                detail="Too many email requests. Please wait a minute and try again.",
            ) from exc
        # Never leak provider internals / enumeration oracle
        raise HTTPException(status_code=400, detail="Could not send magic link. Please check the email and try again.") from exc

    return {"message": "Check your email for a magic link to sign in. It expires in a few minutes."}


# Legacy endpoint kept for API compatibility; the magic-link flow verifies via /auth/callback
@router.post("/otp/verify")
@limiter.limit("5/minute")
def verify_otp(request: Request, response: Response, body: OtpVerifyRequest, db: Session = Depends(get_db)):
    normalized_email = body.email.lower().strip()
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    # Per-email throttle stops distributed brute force of the 6-digit code
    if not _otp_email_allowed(f"verify:{normalized_email}", max_per_hour=_OTP_VERIFY_PER_HOUR):
        raise HTTPException(status_code=429, detail="Too many verification attempts. Please wait and try again.")

    allowed_types = {"email", "magiclink", "signup", "invite", "recovery", "email_change"}
    requested_type = (body.type or "email").strip().lower()
    if requested_type not in allowed_types:
        requested_type = "email"

    last_exc: Exception | None = None
    resp = None
    try:
        resp = get_supabase_client().auth.verify_otp(
            {"email": normalized_email, "token": token, "type": requested_type}
        )
    except Exception as exc:
        last_exc = exc
        if _is_rate_limit_error(exc):
            raise HTTPException(status_code=429, detail="Too many verification attempts. Please wait and try again.") from exc

    if last_exc is not None or resp is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code. Please request a new link.") from last_exc

    supabase_user = getattr(resp, "user", None)
    session = getattr(resp, "session", None)
    if not supabase_user and session:
        supabase_user = getattr(session, "user", None)
    if not supabase_user:
        raise HTTPException(status_code=401, detail="Could not verify code. Please request a new link.")

    email_for_upsert = str(getattr(supabase_user, "email", "") or normalized_email).lower()
    db_user = upsert_local_user(db, str(supabase_user.id), email_for_upsert)

    access_token, refresh_token = _extract_session_data(resp)
    # Fallback: session may be nested inside resp.session already extracted
    if not access_token and session:
        access_token = getattr(session, "access_token", None)
        refresh_token = getattr(session, "refresh_token", None)

    if not access_token:
        raise HTTPException(status_code=401, detail="Verification succeeded but no session was returned. Please try again.")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_type": db_user.user_type,
    }


# Legacy password endpoints reply 410 Gone; Google OAuth remains supported via /oauth/exchange

@router.post("/signup")
def signup_legacy(user: schemas.UserCreate):
    raise HTTPException(
        status_code=410,
        detail="Password sign-up is disabled. Use POST /auth/otp/request with your email to receive a magic link. Google sign-in still works via Supabase OAuth.",
    )


@router.post("/login")
def login_legacy(user: schemas.UserLogin):
    raise HTTPException(
        status_code=410,
        detail="Password login is disabled. Use POST /auth/otp/request with your email to receive a magic link. Google sign-in still works via Supabase OAuth.",
    )


@router.get("/google/callback")
@limiter.limit("10/minute")
def google_callback(request: Request, response: Response, code: str, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=410,
        detail="Google OAuth callback moved to Supabase Auth. Configure Google in Supabase and use the Supabase callback flow.",
    )

@router.get("/verify")
def verify_auth(user = Depends(verify_supabase_token)):
    return {"status": "valid", "user_id": user.id, "email": user.email}


@router.get("/session")
def get_session(user=Depends(verify_supabase_token), db: Session = Depends(get_db)):
    """Unified identity for the single login: owner workspace + agent memberships.

    The frontend routes by role from this payload — one login serves owners and
    human agents, so invited agents are never stranded in an empty owner account.
    """
    from services.supabase_auth import get_identity_overview
    return get_identity_overview(db, user)


@router.post("/refresh")
def refresh_session(payload: RefreshTokenPayload):
    try:
        response = get_supabase_client().auth.refresh_session(payload.refresh_token)
    except Exception:
        try:
            response = get_supabase_client().auth.refresh_session({"refresh_token": payload.refresh_token})
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Could not refresh session") from exc

    access_token, refresh_token = _extract_session_data(response)
    if not access_token:
        raise HTTPException(status_code=401, detail="Could not refresh session")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


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

    db_user.last_reset_date = datetime.now(timezone.utc)

    db.commit()
    db.refresh(db_user)
    
    return {
        "message": "Plans are currently disabled; your workspace has full access.", 
        "user_type": db_user.user_type,
        "credits_remaining": db_user.credits_remaining,
        "next_reset": db_user.last_reset_date + timedelta(days=30)
    }
