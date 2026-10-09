"""Shared helpers for creating and removing knowledge sources outside the upload endpoints."""
import logging
import uuid

from sqlalchemy.orm import Session

from db import models
from services.ingest_queue import enqueue_kb_ingest
from services.kb_limits import enforce_text_limit
from services.kb_source_storage import delete_kb_source, store_kb_source
from services.vector_store import delete_for_kb

logger = logging.getLogger(__name__)


class KBQueueFullError(RuntimeError):
    pass


async def create_text_kb(db: Session, agent: models.Agent, title: str, text: str) -> models.KnowledgeBase:
    """Store `text` as a text source and queue it for indexing (same path as a pasted-text source)."""
    extracted_size = enforce_text_limit(text)
    data = text.encode("utf-8")
    stored = await store_kb_source(data, f"{title[:80]}.txt", "text/plain")
    kb = models.KnowledgeBase(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        source_type=models.KBSourceType.text,
        source_uri=None,
        title=title,
        status=models.KBStatus.pending,
        original_filename=title,
        source_storage_url=stored.url,
        source_storage_key=stored.key,
        source_content_type=stored.content_type,
        source_content_sha256=stored.sha256,
        file_size_bytes=len(data),
        extracted_size_bytes=extracted_size,
    )
    db.add(kb)
    db.flush()
    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()
    db.refresh(kb)
    if not enqueue_kb_ingest(str(job.id), text):
        raise KBQueueFullError("Knowledge ingestion queue is full. Please try again shortly.")
    return kb


async def delete_kb_completely(db: Session, kb: models.KnowledgeBase, agent: models.Agent) -> None:
    """Remove a source's vectors, stored file, and row."""
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_for_kb(cfg.vector_store_namespace, str(kb.id))
        except Exception:
            logger.exception("failed_to_delete_kb_vectors kb_id=%s", kb.id)
    await delete_kb_source(kb.source_storage_key)
    db.delete(kb)
    db.commit()
