import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db import models


DEFAULT_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))


def delete_old_conversation_data(db: Session, days: int = DEFAULT_RETENTION_DAYS) -> dict[str, int]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    chat_deleted = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    usage_deleted = (
        db.query(models.UsageLog)
        .filter(models.UsageLog.timestamp < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"chat_messages_deleted": chat_deleted, "usage_logs_deleted": usage_deleted}
