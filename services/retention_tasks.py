import os

from db.database import SessionLocal
from services.celery_app import celery_app
from services.retention import DEFAULT_RETENTION_DAYS, delete_old_conversation_data


def _retention_days(days: int | None) -> int:
    if days:
        return days
    return int(os.getenv("DATA_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))


@celery_app.task(name="retention.cleanup_conversation_data")
def cleanup_conversation_data(days: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    try:
        return delete_old_conversation_data(db, days=_retention_days(days))
    finally:
        db.close()
