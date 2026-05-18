import os

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import schemas
from services.rate_limit import limiter_storage_options
from services.supabase_auth import get_supabase_client

limiter = Limiter(key_func=get_remote_address, **limiter_storage_options())
router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL")


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    body: schemas.ForgotPasswordRequest,
):
    normalized_email = body.email.lower()
    options = {"redirect_to": f"{FRONTEND_URL}/reset-password"} if FRONTEND_URL else None
    try:
        if options:
            get_supabase_client().auth.reset_password_email(normalized_email, options=options)
        else:
            get_supabase_client().auth.reset_password_email(normalized_email)
    except Exception:
        pass
    return {"message": "If that email exists, a password reset link has been sent"}


@router.post("/reset-password")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    body: schemas.ResetPasswordRequest,
):
    raise HTTPException(
        status_code=410,
        detail=(
            "Password reset is handled by Supabase Auth. Use the Supabase recovery session "
            "on the frontend to update the password."
        ),
    )
