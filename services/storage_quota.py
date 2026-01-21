import os
from sqlalchemy.orm import Session
from db import models
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

# Storage limits in bytes (from MB in env)
FREE_STORAGE_LIMIT = int(os.getenv("FREE_STORAGE_LIMIT_MB", "2")) * 1024 * 1024
PAID_STORAGE_LIMIT = int(os.getenv("PAID_STORAGE_LIMIT_MB", "50")) * 1024 * 1024
PRO_STORAGE_LIMIT = int(os.getenv("PRO_STORAGE_LIMIT_MB", "100")) * 1024 * 1024

# File count limits
FREE_FILES_LIMIT = 5
PAID_FILES_LIMIT = 50
PRO_FILES_LIMIT = 999999  # Unlimited


def get_storage_limit(user_type: str) -> int:
    # Get storage limit in bytes for user tier
    if user_type == "free":
        return FREE_STORAGE_LIMIT
    elif user_type == "paid":
        return PAID_STORAGE_LIMIT
    elif user_type == "pro":
        return PRO_STORAGE_LIMIT
    return FREE_STORAGE_LIMIT


def get_files_limit(user_type: str) -> int:
    # Get file count limit for user tier
    if user_type == "free":
        return FREE_FILES_LIMIT
    elif user_type == "paid":
        return PAID_FILES_LIMIT
    elif user_type == "pro":
        return PRO_FILES_LIMIT
    return FREE_FILES_LIMIT


def get_or_create_storage_usage(db: Session, user_id: int) -> models.UserStorageUsage:
    # Get or create storage usage record for user
    usage = db.query(models.UserStorageUsage).filter(
        models.UserStorageUsage.user_id == user_id
    ).first()
    
    if not usage:
        usage = models.UserStorageUsage(user_id=user_id)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    
    return usage


def check_storage_quota(db: Session, user: models.User, additional_bytes: int = 0) -> None:
    # Check if user has sufficient storage quota, raise HTTPException if exceeded
    usage = get_or_create_storage_usage(db, user.id)
    limit = get_storage_limit(user.user_type)
    
    if usage.total_size_bytes + additional_bytes > limit:
        limit_mb = limit / (1024 * 1024)
        current_mb = usage.total_size_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=403,
            detail=f"Storage quota exceeded. Your {user.user_type} plan allows {limit_mb:.1f}MB, you're using {current_mb:.1f}MB"
        )


def check_files_quota(db: Session, user: models.User) -> None:
    # Check if user has reached file count limit, raise HTTPException if exceeded
    usage = get_or_create_storage_usage(db, user.id)
    limit = get_files_limit(user.user_type)
    
    if usage.total_files >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"File limit reached. Your {user.user_type} plan allows {limit} files, upgrade to add more"
        )


def increment_storage_usage(db: Session, user_id: int, file_size_bytes: int, chunk_count: int = 0) -> None:
    # Increment user's storage usage counters
    usage = get_or_create_storage_usage(db, user_id)
    usage.total_files += 1
    usage.total_size_bytes += file_size_bytes
    usage.total_chunks += chunk_count
    from datetime import datetime
    usage.last_updated = datetime.utcnow()
    db.commit()


def decrement_storage_usage(db: Session, user_id: int, file_size_bytes: int, chunk_count: int = 0) -> None:
    # Decrement user's storage usage counters
    usage = get_or_create_storage_usage(db, user_id)
    usage.total_files = max(0, usage.total_files - 1)
    usage.total_size_bytes = max(0, usage.total_size_bytes - file_size_bytes)
    usage.total_chunks = max(0, usage.total_chunks - chunk_count)
    from datetime import datetime
    usage.last_updated = datetime.utcnow()
    db.commit()


def get_storage_stats(db: Session, user: models.User) -> dict:
    # Get storage statistics for user
    usage = get_or_create_storage_usage(db, user.id)
    storage_limit = get_storage_limit(user.user_type)
    files_limit = get_files_limit(user.user_type)
    
    return {
        "user_type": user.user_type,
        "total_files": usage.total_files,
        "files_limit": files_limit,
        "total_size_bytes": usage.total_size_bytes,
        "total_size_mb": round(usage.total_size_bytes / (1024 * 1024), 2),
        "storage_limit_bytes": storage_limit,
        "storage_limit_mb": round(storage_limit / (1024 * 1024), 2),
        "storage_used_percent": round((usage.total_size_bytes / storage_limit) * 100, 1) if storage_limit > 0 else 0,
        "total_chunks": usage.total_chunks,
        "last_updated": usage.last_updated
    }
