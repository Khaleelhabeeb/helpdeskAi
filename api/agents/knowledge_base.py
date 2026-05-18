import anyio
import logging
import uuid as uuid_lib
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from api.scrape.scrape import scrape_url_content
from db import models, schemas
from services import cache_keys
from services.file_parser import extract_text_from_file
from services.ingest_queue import enqueue_kb_ingest
from services.kb_limits import PayloadTooLargeError, enforce_text_limit, read_upload_limited
from services.redis_client import cache_delete
from services.vector_store import delete_for_kb
from utils.jwt import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def validate_uuid(uuid_str: str) -> bool:
    try:
        uuid_lib.UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False


@router.post("/add", response_model=schemas.KnowledgeBaseOut)
async def add_knowledge_base(
    agent_id: str = Form(...),
    source_type: schemas.KBSourceType = Form(...),
    title: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    structured_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == agent_id, models.Agent.user_id == user.id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    provided = [bool(url), bool(structured_text), bool(file)]
    if sum(provided) != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one of: url, structured_text, file")

    source_uri = None
    original_filename = None
    file_size_bytes = 0
    extracted_size_bytes = 0
    extracted_text = ""

    if source_type in (schemas.KBSourceType.upload_pdf, schemas.KBSourceType.upload_txt, schemas.KBSourceType.other):
        if not file:
            raise HTTPException(status_code=400, detail="File is required for upload_* source types")

        try:
            file_content = await read_upload_limited(file)
        except PayloadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        file_size_bytes = len(file_content)

        kb_id = str(uuid_lib.uuid4())
        original_filename = file.filename or f"upload-{kb_id}"
        try:
            extracted_text = await anyio.to_thread.run_sync(extract_text_from_file, file_content, original_filename)
            extracted_size_bytes = enforce_text_limit(extracted_text)
        except PayloadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        source_uri = original_filename

    elif source_type == schemas.KBSourceType.url:
        if not url:
            raise HTTPException(status_code=400, detail="url is required for source_type=url")

        scraped_data = await scrape_url_content(url)
        extracted_text = scraped_data.get("text", "")
        try:
            extracted_size_bytes = enforce_text_limit(extracted_text)
        except PayloadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc

        kb_id = str(uuid_lib.uuid4())
        source_uri = url
        original_filename = scraped_data.get("title", url)

    elif source_type == schemas.KBSourceType.text:
        if not structured_text:
            raise HTTPException(status_code=400, detail="structured_text is required for source_type=text")

        try:
            extracted_size_bytes = enforce_text_limit(structured_text)
        except PayloadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc

        kb_id = str(uuid_lib.uuid4())
        extracted_text = structured_text
        source_uri = None
        original_filename = title or "Structured Text"

    else:
        raise HTTPException(status_code=400, detail="Unsupported source_type")

    kb = models.KnowledgeBase(
        id=kb_id,
        agent_id=agent.id,
        source_type=models.KBSourceType(source_type.value),
        source_uri=source_uri,
        title=title or original_filename,
        status=models.KBStatus.pending,
        original_filename=original_filename,
        file_size_bytes=file_size_bytes,
        extracted_size_bytes=extracted_size_bytes,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()

    if not enqueue_kb_ingest(str(job.id), extracted_text):
        raise HTTPException(
            status_code=503,
            detail="Knowledge ingestion queue is full. Please try again shortly.",
        )
    cache_delete(cache_keys.dashboard_summary(user.id))

    return kb


@router.get("/{agent_id}", response_model=list[schemas.KnowledgeBaseOut])
def list_kbs(
    agent_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of KBs to return"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == agent_id, models.Agent.user_id == user.id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.agent_id == agent.id
    ).offset(skip).limit(limit).all()


@router.delete("/{kb_id}")
def delete_kb(kb_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")

    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")

    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_for_kb(cfg.vector_store_namespace, str(kb.id))
        except Exception:
            logger.exception("failed_to_delete_kb_vectors kb_id=%s", kb_id)

    db.delete(kb)
    db.commit()
    cache_delete(cache_keys.dashboard_summary(user.id))
    return {"message": "KB deleted"}


@router.post("/{kb_id}/reindex", response_model=schemas.KBIngestJobOut)
async def reindex_kb(kb_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")

    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")

    transient_text = None
    if kb.source_type == models.KBSourceType.url and kb.source_uri:
        scraped_data = await scrape_url_content(kb.source_uri)
        transient_text = scraped_data.get("text", "")
        try:
            enforce_text_limit(transient_text)
        except PayloadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
    elif kb.source_type != models.KBSourceType.url:
        raise HTTPException(
            status_code=400,
            detail="File/text sources must be uploaded again to retrain because raw source text is not stored.",
        )

    kb.status = models.KBStatus.pending
    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()
    db.refresh(job)
    if not enqueue_kb_ingest(str(job.id), transient_text or ""):
        raise HTTPException(
            status_code=503,
            detail="Knowledge ingestion queue is full. Please try again shortly.",
        )
    cache_delete(cache_keys.dashboard_summary(user.id))
    return job


@router.get("/{kb_id}/content")
async def get_kb_content(kb_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")

    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")

    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")

    raise HTTPException(
        status_code=410,
        detail="Raw knowledge content is not stored after embedding. Only vectors and metadata are retained.",
    )


@router.get("/{kb_id}/download")
def get_kb_download_url(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    # Original binary file storage is disabled; URL sources can still be opened.
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    if kb.source_type != models.KBSourceType.url or not kb.source_uri:
        raise HTTPException(status_code=404, detail="No original file available for download")

    return {
        "kb_id": kb_id,
        "filename": kb.original_filename,
        "download_url": kb.source_uri,
        "expires_in_seconds": None
    }


@router.get("/{kb_id}/details", response_model=schemas.KnowledgeBaseOut)
def get_kb_details(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    """Get detailed information about a specific knowledge base entry"""
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden - not your agent")
    
    return kb


@router.patch("/{kb_id}")
def update_kb_metadata(
    kb_id: str,
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Update KB metadata (currently only title)"""
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden - not your agent")
    
    if title is not None:
        kb.title = title
    
    db.commit()
    db.refresh(kb)
    
    return {"message": "KB updated successfully", "kb": kb}


@router.get("/{kb_id}/status")
def get_kb_ingestion_status(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    """
    Check the ingestion/vectorization status of a KB entry.
    Returns KB status and associated job information.
    """
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden - not your agent")
    
    # Get latest ingest job for this KB
    latest_job = db.query(models.KBIngestJob).filter(
        models.KBIngestJob.kb_id == kb_id
    ).order_by(models.KBIngestJob.created_at.desc()).first()
    
    response = {
        "kb_id": kb_id,
        "kb_status": kb.status.value,  # pending, ready, failed
        "chunk_count": kb.chunk_count,
        "file_size_bytes": kb.file_size_bytes,
        "extracted_size_bytes": kb.extracted_size_bytes,
        "original_filename": kb.original_filename,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None
    }
    
    if latest_job:
        response["latest_job"] = {
            "job_id": str(latest_job.id),
            "state": latest_job.state.value,  # queued, running, succeeded, failed
            "error_message": latest_job.error,
            "total_chunks": latest_job.total_chunks,
            "processed_chunks": latest_job.processed_chunks,
            "created_at": latest_job.created_at.isoformat() if latest_job.created_at else None
        }
    else:
        response["latest_job"] = None
    
    return response
