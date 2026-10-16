import asyncio
import logging
import os
import tempfile
import threading
import time
import uuid as uuid_lib
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import BoundedSemaphore
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from db import models
from db.database import BackgroundSession
from services.http_client import close_http_clients
from services.ingest_worker import process_kb_ingest_job
from services.redis_client import close_redis_clients


logger = logging.getLogger(__name__)

_MAX_WORKERS = int(os.getenv("KB_INGEST_WORKERS", "1"))
_MAX_PENDING = int(os.getenv("KB_INGEST_QUEUE_SIZE", "25"))
_SPOOL_DIR = Path(os.getenv("KB_INGEST_SPOOL_DIR", "/tmp/helpdeskai-ingest"))
# Upper bound on how long extracted customer text may linger on local disk when a
# job fails before success (success and KB delete remove it immediately).
_SPOOL_MAX_AGE_HOURS = int(os.getenv("KB_INGEST_SPOOL_MAX_AGE_HOURS", "48"))
# Grace period before an unreferenced spool file is treated as an orphan.
_SPOOL_ORPHAN_GRACE_SECONDS = int(os.getenv("KB_INGEST_SPOOL_ORPHAN_GRACE_SECONDS", "3600"))
# A recovery claim older than this is assumed to belong to a dead replica and
# may be taken over by another instance booting later.
_CLAIM_STALE_MINUTES = int(os.getenv("KB_INGEST_CLAIM_STALE_MINUTES", "10"))

_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="kb-ingest")
_slots = BoundedSemaphore(_MAX_PENDING)


def describe_spool_config() -> dict:
    """Effective spool settings, for startup logging."""
    return {
        "dir": str(_SPOOL_DIR),
        "max_age_hours": _SPOOL_MAX_AGE_HOURS,
        "orphan_grace_seconds": _SPOOL_ORPHAN_GRACE_SECONDS,
    }


def _mark_job_failed(job_id: str, error: str) -> None:
    db = BackgroundSession()
    try:
        job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
        if job:
            job.state = models.JobState.failed
            job.error = error
            job.claimed_by = None
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
        path = handle.name
    # Spool holds raw customer text, however briefly: owner-read-only.
    try:
        os.chmod(path, 0o600)
    except OSError:
        logger.warning("failed_to_chmod_ingest_spool path=%s", path)
    return path


def _persist_spool_path(job_id: str, spool_path: str) -> None:
    db = BackgroundSession()
    try:
        job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
        if job:
            job.transient_spool_path = spool_path
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed_to_persist_spool_path job_id=%s", job_id)
    finally:
        db.close()


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


def enqueue_kb_ingest(
    job_id: str,
    transient_text: Optional[str] = None,
    reuse_spool_path: Optional[str] = None,
) -> bool:
    """Queue an ingest job. Spool text to disk (persisting the path on the job
    row for crash recovery) or reuse an existing spool file from a prior job."""
    if not _slots.acquire(blocking=False):
        message = "Knowledge ingestion queue is full. Please try again shortly."
        _mark_job_failed(job_id, message)
        logger.warning("ingest_queue_full job_id=%s", job_id)
        return False

    spool_path: Optional[str] = None
    wrote_spool = False
    try:
        if reuse_spool_path and Path(reuse_spool_path).is_file():
            spool_path = reuse_spool_path
        elif transient_text is not None:
            spool_path = _write_spool_file(job_id, transient_text)
            wrote_spool = True
        if spool_path:
            _persist_spool_path(job_id, spool_path)
        future = _executor.submit(_run_job, job_id, spool_path)
        future.add_done_callback(_release_slot)
        logger.info("ingest_job_enqueued job_id=%s", job_id)
        return True
    except Exception as exc:
        _slots.release()
        if wrote_spool and spool_path:
            try:
                Path(spool_path).unlink(missing_ok=True)
            except Exception:
                logger.warning("failed_to_remove_ingest_spool path=%s", spool_path)
        _mark_job_failed(job_id, str(exc))
        logger.exception("failed_to_enqueue_ingest_job job_id=%s", job_id)
        return False


def find_reusable_spool_path(db: Session, kb_id: str) -> Optional[str]:
    """Newest on-disk spool file for a KB, if any. Lets retrain retry a failed
    ingest without the customer re-uploading; bounded by the orphan sweeper."""
    jobs = (
        db.query(models.KBIngestJob)
        .filter(
            models.KBIngestJob.kb_id == kb_id,
            models.KBIngestJob.transient_spool_path.isnot(None),
        )
        .order_by(models.KBIngestJob.created_at.desc())
        .limit(5)
        .all()
    )
    for job in jobs:
        path = job.transient_spool_path
        if path and Path(path).is_file():
            return path
    return None


def delete_spools_for_kb(db: Session, kb_id: str) -> int:
    """Remove all spool files (and their job references) for a KB. Used on KB
    delete so failed-job text never lingers after the source is gone."""
    removed = 0
    jobs = (
        db.query(models.KBIngestJob)
        .filter(
            models.KBIngestJob.kb_id == kb_id,
            models.KBIngestJob.transient_spool_path.isnot(None),
        )
        .all()
    )
    for job in jobs:
        path = job.transient_spool_path
        job.transient_spool_path = None
        if path:
            try:
                Path(path).unlink(missing_ok=True)
                removed += 1
            except Exception:
                logger.warning("failed_to_remove_ingest_spool path=%s", path)
    return removed


def recover_interrupted_jobs() -> dict:
    """Re-enqueue jobs left queued/running by a crash. URL sources re-scrape;
    file/text sources resume from their spool file; spool-less file/text jobs
    are marked failed (customer re-uploads). Runs once at startup.

    Multi-replica safe: each stuck job is claimed with an ownership token via
    one atomic UPDATE, so when several instances boot together only one of
    them takes each job. Stale claims (owner died mid-recovery) become
    claimable again after `_CLAIM_STALE_MINUTES`.
    """
    summary = {"resubmitted": 0, "failed": 0, "skipped": 0}
    token = uuid_lib.uuid4().hex
    stale_before = datetime.now(timezone.utc) - timedelta(minutes=_CLAIM_STALE_MINUTES)
    db = BackgroundSession()
    try:
        updated = (
            db.query(models.KBIngestJob)
            .filter(
                models.KBIngestJob.state.in_([models.JobState.queued, models.JobState.running]),
                or_(
                    models.KBIngestJob.claimed_by.is_(None),
                    models.KBIngestJob.updated_at < stale_before,
                ),
            )
            .update({models.KBIngestJob.claimed_by: token}, synchronize_session=False)
        )
        db.commit()
        if not updated:
            return summary
        stuck = (
            db.query(models.KBIngestJob)
            .filter(models.KBIngestJob.claimed_by == token)
            .order_by(models.KBIngestJob.created_at.asc())
            .all()
        )
        for job in stuck:
            job_id = str(job.id)
            kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
            if kb is None:
                _mark_job_failed(job_id, "KB not found")
                summary["failed"] += 1
                continue
            spool_path = job.transient_spool_path
            spool_ok = bool(spool_path and Path(spool_path).is_file())
            if kb.source_type == models.KBSourceType.url or spool_ok:
                # Blocking acquire: at startup the executor is fresh; every
                # interrupted job deserves a slot rather than a spurious failure.
                _slots.acquire()
                try:
                    future = _executor.submit(_run_job, job_id, spool_path if spool_ok else None)
                    future.add_done_callback(_release_slot)
                    summary["resubmitted"] += 1
                except Exception:
                    _slots.release()
                    _mark_job_failed(job_id, "Could not resume ingestion after restart")
                    summary["failed"] += 1
            else:
                _mark_job_failed(
                    job_id,
                    "Ingestion was interrupted before finishing. Upload the source again.",
                )
                summary["failed"] += 1
    except Exception:
        logger.exception("ingest_recovery_failed")
    finally:
        db.close()
    logger.info("ingest_recovery_complete resubmitted=%d failed=%d", summary["resubmitted"], summary["failed"])
    return summary


def sweep_orphan_spools() -> dict:
    """Delete spool files no live job needs, plus stale failure spools past the
    max age (those KBs then require re-upload to retrain). Also clears spool
    references pointing at already-removed files."""
    summary = {"removed_files": 0, "cleared_refs": 0}
    try:
        _SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        logger.exception("ingest_spool_dir_unavailable")
        return summary
    db = BackgroundSession()
    try:
        referenced: set[str] = set()
        live_terminal_cutoff = time.time() - _SPOOL_MAX_AGE_HOURS * 3600
        rows = (
            db.query(models.KBIngestJob)
            .filter(models.KBIngestJob.transient_spool_path.isnot(None))
            .all()
        )
        for row in rows:
            path = row.transient_spool_path
            if not path:
                continue
            is_live = row.state in (models.JobState.queued, models.JobState.running)
            if not Path(path).is_file():
                # Only clear terminal rows: a live job's spool may live on a
                # sibling replica's disk (autoscaling), not this one.
                if not is_live:
                    row.transient_spool_path = None
                    summary["cleared_refs"] += 1
                continue
            if is_live:
                referenced.add(path)
                continue
            # Terminal job: keep a recent failure spool for retrain retry,
            # otherwise let it age out.
            try:
                mtime = Path(path).stat().st_mtime
            except OSError:
                row.transient_spool_path = None
                summary["cleared_refs"] += 1
                continue
            if mtime < live_terminal_cutoff:
                try:
                    Path(path).unlink(missing_ok=True)
                    summary["removed_files"] += 1
                except Exception:
                    logger.warning("failed_to_remove_ingest_spool path=%s", path)
                row.transient_spool_path = None
                summary["cleared_refs"] += 1
            else:
                referenced.add(path)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("ingest_spool_sweep_db_failed")
    finally:
        db.close()

    # Files with no referencing row at all (e.g. DB was wiped): age-based removal.
    now = time.time()
    try:
        for path in _SPOOL_DIR.glob("*.txt"):
            try:
                if str(path) in referenced:
                    continue
                if now - path.stat().st_mtime < _SPOOL_ORPHAN_GRACE_SECONDS:
                    continue
                path.unlink(missing_ok=True)
                summary["removed_files"] += 1
            except Exception:
                logger.warning("failed_to_remove_ingest_spool path=%s", path)
    except Exception:
        logger.exception("ingest_spool_sweep_fs_failed")
    if summary["removed_files"] or summary["cleared_refs"]:
        logger.info(
            "ingest_spool_sweep_complete removed_files=%d cleared_refs=%d",
            summary["removed_files"],
            summary["cleared_refs"],
        )
    return summary
