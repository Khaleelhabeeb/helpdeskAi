import logging
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db.database import SessionLocal
from db import models
from services.rag_service import index_kb_text
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def process_kb_ingest_job(
    job_id: str,
    transient_text: Optional[str] = None,
    transient_text_path: Optional[str] = None,
) -> None:
    """
    Worker function to process a KB ingest job.
    - Looks up the job and KB
    - Marks job running, then succeeded/failed
    - Sets KB status accordingly
    - Does NOT store chunks or embeddings in Postgres
    - Writes embeddings to the configured vector store

    transient_text_path: temporary spool file supplied by the ingest queue.
    """
    db: Session = SessionLocal()
    try:
        job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
        if not job:
            return
        kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
        if not kb:
            job.state = models.JobState.failed
            job.error = "KB not found"
            db.commit()
            return

        # Mark running
        job.state = models.JobState.running
        job.processed_chunks = 0
        job.total_chunks = None
        db.commit()

        # Read minimal info for vector upsert
        agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id).first()
        config = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == kb.agent_id).first()
        namespace = config.vector_store_namespace if config else None

        text_content: Optional[str] = None
        
        if transient_text_path:
            text_content = Path(transient_text_path).read_text(encoding="utf-8")
        elif transient_text is not None and len(transient_text.strip()) > 0:
            text_content = transient_text

        if not text_content or len(text_content.strip()) == 0:
            raise ValueError("No text content extracted for KB")

        if not agent:
            raise ValueError("Agent not found for KB")
        if not namespace:
            raise ValueError("Missing vector store namespace")

        def update_progress(done_chunks: int, total_chunks: int) -> None:
            job.total_chunks = total_chunks
            job.processed_chunks = done_chunks
            kb.chunk_count = done_chunks
            db.commit()

        chunk_count = index_kb_text(
            db=db,
            user_id=agent.user_id,
            agent_id=str(agent.id),
            kb_id=str(kb.id),
            namespace=namespace,
            text_value=text_content,
            on_batch=update_progress,
        )

        # Update KB with chunk count
        kb.chunk_count = chunk_count
        kb.status = models.KBStatus.ready
        
        # Mark job success
        job.state = models.JobState.succeeded
        job.error = None
        db.commit()
    except Exception as e:
        logger.exception("kb_ingest_job_failed job_id=%s", job_id)
        try:
            job = db.query(models.KBIngestJob).filter(models.KBIngestJob.id == job_id).first()
            if job:
                job.state = models.JobState.failed
                job.error = str(e)
                kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == job.kb_id).first()
                if kb:
                    kb.status = models.KBStatus.failed
            db.commit()
        except SQLAlchemyError:
            db.rollback()
    finally:
        if transient_text_path:
            try:
                Path(transient_text_path).unlink(missing_ok=True)
            except Exception:
                logger.warning("failed_to_remove_ingest_spool path=%s", transient_text_path)
        db.close()
