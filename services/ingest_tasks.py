import asyncio
import logging

from services.celery_app import celery_app
from services.ingest_worker import process_kb_ingest_job


logger = logging.getLogger(__name__)


@celery_app.task(name="kb_ingest.process", bind=True)
def process_kb_ingest_job_task(self, job_id: str, spool_path: str) -> None:
    logger.info("celery_ingest_started job_id=%s task_id=%s", job_id, self.request.id)
    asyncio.run(process_kb_ingest_job(job_id, transient_text_path=spool_path))
