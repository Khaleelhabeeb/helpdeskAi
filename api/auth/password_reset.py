from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import os

from db.database import SessionLocal
from db import schemas
from db import models
from utils.security import hash_password
from services.email import send_email

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_reset_token() -> str:
    """Generate a secure random token for password reset."""
    return secrets.token_urlsafe(32)


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    body: schemas.ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    normalized_email = body.email.lower()
    user = db.query(models.User).filter(models.User.email == normalized_email).first()
    
    if not user:
        return {"message": "If that email exists, a password reset link has been sent"}
    
    reset_token = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    user.reset_token = reset_token
    user.reset_token_expires = expires_at
    db.commit()
    
    # Send email with reset link
    reset_url = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4a6cf7;">Reset Your Password</h2>
                <p>You requested to reset your password for your HelpDeskAi account.</p>
                <p>Click the button below to reset your password. This link will expire in 1 hour.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #4a6cf7; 
                              color: white; 
                              padding: 12px 30px; 
                              text-decoration: none; 
                              border-radius: 5px; 
                              display: inline-block;">
                        Reset Password
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    If you didn't request this, please ignore this email. Your password will remain unchanged.
                </p>
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{reset_url}" style="color: #4a6cf7;">{reset_url}</a>
                </p>
            </div>
        </body>
    </html>
    """
    
    send_email(
        subject="Reset Your Password - HelpDeskAi",
        html_content=html_content,
        to_email=user.email,
        to_name=user.email.split("@")[0]
    )
    
    return {"message": "If that email exists, a password reset link has been sent"}


@router.post("/reset-password")
@limiter.limit("5/hour")
async def reset_password(
    request: Request,
    body: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.reset_token == body.token
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Check if token is expired
    if not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        # Clean up expired token
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one")
    
    # Update password and clear reset token
    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    
    # Send confirmation email
    html_content = """
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4a6cf7;">Password Reset Successful</h2>
                <p>Your password has been successfully reset.</p>
                <p>You can now log in to your HelpDeskAi account with your new password.</p>
                <p style="color: #666; font-size: 14px; margin-top: 30px;">
                    If you didn't make this change, please contact our support team immediately.
                </p>
            </div>
        </body>
    </html>
    """
    
    send_email(
        subject="Password Reset Successful - HelpDeskAi",
        html_content=html_content,
        to_email=user.email,
        to_name=user.email.split("@")[0]
    )
    
    return {"message": "Password reset successful. You can now log in with your new password"}
