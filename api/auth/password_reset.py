from fastapi import APIRouter, HTTPException, Request, Response
import os

from db import schemas
from services.supabase_auth import get_supabase_client
from utils.rate_limit import create_limiter

limiter = create_limiter()
router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL")


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "too many requests" in msg or "rate limit" in msg


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    response: Response,
    body: schemas.ForgotPasswordRequest,
):
    """Deprecated alias for /auth/otp/request, kept so older clients still receive a sign-in email."""
    normalized_email = body.email.lower().strip()
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
            raise HTTPException(status_code=429, detail="Too many email requests. Please wait and try again.") from exc
        # Swallow errors to avoid email enumeration
        pass
    return {"message": "Check your email for a magic link to sign in. It expires in a few minutes."}


@router.post("/reset-password")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    response: Response,
    body: schemas.ResetPasswordRequest,
):
    raise HTTPException(
        status_code=410,
        detail="Password authentication is removed. Use POST /auth/otp/request with your email to receive a magic link. Google sign-in still works via Supabase OAuth.",
    )
