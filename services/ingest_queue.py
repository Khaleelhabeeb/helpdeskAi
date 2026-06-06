import asyncio
import logging
import os
import tempfile
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import BoundedSemaphore
from typing import Optional

from db import models
from db.database import BackgroundSession
from services.http_client import close_http_clients
from services.ingest_worker import process_kb_ingest_job
from services.redis_client import close_redis_clients


logger = logging.getLogger(__name__)

_MAX_WORKERS = int(os.getenv("KB_INGEST_WORKERS", "1"))
_MAX_PENDING = int(os.getenv("KB_INGEST_QUEUE_SIZE", "25"))
_SPOOL_DIR = Path(os.getenv("KB_INGEST_SPOOL_DIR", "/tmp/helpdeskai-ingest"))

_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="kb-ingest")
_slots = BoundedSemaphore(_MAX_PENDING)


def _mark_job_failed(job_id: str, error: str) -> None:
    db = BackgroundSession()
    try:
        job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
        if job:
            job.state = models.JobState.failed
            job.error = error
            job.updated_at = datetime.now(timezone.utc)
            kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
            if kb:
                kb.status = models.KBStatus.failed
                kb.updated_at = datetime.now(timezone.utc)
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


def _release_slot(future: Future) -> None:
    try:
        try:
            exc = future.exception()
        except BaseException as exc:
            logger.error("ingest_worker_future_failed", exc_info=(type(exc), exc, exc.__traceback__))
            return
        if exc:
            logger.error("ingest_worker_crashed", exc_info=(type(exc), exc, exc.__traceback__))
    finally:
        _slots.release()


# Cache one event loop per thread instead of creating one per job
# via asyncio.run().  Saves ~200-500KB of temporary allocation per job.
_thread_loops: dict[int, asyncio.AbstractEventLoop] = {}

def _get_thread_loop() -> asyncio.AbstractEventLoop:
    tid = threading.get_ident()
    loop = _thread_loops.get(tid)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_loops[tid] = loop
    return loop


async def _run_async_job(job_id: str, spool_path: Optional[str]) -> None:
    try:
        await process_kb_ingest_job(job_id, transient_text_path=spool_path)
    finally:
        await close_http_clients()
        await close_redis_clients()


def _run_job(job_id: str, spool_path: Optional[str]) -> None:
    loop = _get_thread_loop()
    loop.run_until_complete(_run_async_job(job_id, spool_path))


def enqueue_kb_ingest(job_id: str, transient_text: Optional[str] = None) -> bool:
    if not _slots.acquire(blocking=False):
        message = "Knowledge ingestion queue is full. Please try again shortly."
        _mark_job_failed(job_id, message)
        logger.warning("ingest_queue_full job_id=%s", job_id)
        return False

    spool_path: Optional[str] = None
    try:
        if transient_text is not None:
            spool_path = _write_spool_file(job_id, transient_text)
        future = _executor.submit(_run_job, job_id, spool_path)
        future.add_done_callback(_release_slot)
        logger.info("ingest_job_enqueued job_id=%s", job_id)
        return True
    except Exception as exc:
        _slots.release()
        if spool_path:
            try:
                Path(spool_path).unlink(missing_ok=True)
            except Exception:
                logger.warning("failed_to_remove_ingest_spool path=%s", spool_path)
        _mark_job_failed(job_id, str(exc))
        logger.exception("failed_to_enqueue_ingest_job job_id=%s", job_id)
        return False
