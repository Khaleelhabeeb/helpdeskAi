import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from db import models
from db.database import SessionLocal


logger = logging.getLogger(__name__)

_SPOOL_DIR = Path(os.getenv("KB_INGEST_SPOOL_DIR", "/tmp/helpdeskai-ingest"))


def _mark_job_failed(job_id: str, error: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
        if job:
            job.state = models.JobState.failed
            job.error = error
            job.updated_at = datetime.utcnow()
            kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
            if kb:
                kb.status = models.KBStatus.failed
                kb.updated_at = datetime.utcnow()
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed_to_mark_ingest_job_failed job_id=%s", job_id)
    finally:
        db.close()


def _write_spool_file(job_id: str, text: str) -> str:
    _SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f"{job_id}-",
        suffix=".txt",
        dir=_SPOOL_DIR,
        delete=False,
    ) as handle:
        handle.write(text)
        return handle.name


def _remove_spool_file(spool_path: str) -> None:
    try:
        Path(spool_path).unlink(missing_ok=True)
    except Exception:
        logger.warning("failed_to_remove_ingest_spool path=%s", spool_path)


def enqueue_kb_ingest(job_id: str, transient_text: str) -> bool:
    spool_path = ""
    try:
        from services.ingest_tasks import process_kb_ingest_job_task

        spool_path = _write_spool_file(job_id, transient_text)
        result = process_kb_ingest_job_task.delay(job_id, spool_path)
        logger.info("ingest_job_enqueued job_id=%s task_id=%s", job_id, result.id)
        return True
    except Exception as exc:
        if spool_path:
            _remove_spool_file(spool_path)
        _mark_job_failed(job_id, str(exc))
        logger.exception("failed_to_enqueue_ingest_job job_id=%s", job_id)
        return False
