from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from db import schemas
from api.auth.auth import get_db
from db import models
from utils.jwt import get_current_user
import uuid as uuid_lib
from services.ingest_worker import process_kb_ingest_job
from services.vector_store import delete_for_kb
from services.s3_storage import upload_file_to_s3, upload_text_to_s3, delete_kb_files, get_presigned_url, download_text_from_s3, get_s3_key
from services.cloudflare_storage import WorkerUploadError, download_text_from_url, upload_extracted_text, upload_knowledge_file
from services.storage_quota import check_storage_quota, check_files_quota, increment_storage_usage, decrement_storage_usage
from services.file_parser import extract_text_from_file, extract_text_from_pdf, extract_text_from_txt
from api.scrape.scrape import scrape_url_content
import json

router = APIRouter()


def validate_uuid(uuid_str: str) -> bool:
    # Validate if string is a valid UUID
    try:
        uuid_lib.UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False


async def try_upload_extracted_text(text: str, filename: str) -> Optional[str]:
    try:
        upload = await upload_extracted_text(text, filename)
        return upload.url
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        response_text = getattr(exc, "response_text", None)
        print(
            "[WARN /kb/add] Extracted text worker upload failed "
            f"status={status_code} detail={response_text or str(exc)}"
        )
        return None

@router.post("/add", response_model=schemas.KnowledgeBaseOut)
async def add_knowledge_base(
    agent_id: str = Form(...),
    source_type: schemas.KBSourceType = Form(...),
    title: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    structured_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):  
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        print(f"[DEBUG /kb/add] ERROR: Agent not found - agent_id: {agent_id}, user_id: {user.id}")
        raise HTTPException(status_code=404, detail="Agent not found")

    provided = [bool(url), bool(structured_text), bool(file)]
    print(f"[DEBUG /kb/add] Source validation - url: {bool(url)}, structured_text: {bool(structured_text)}, file: {bool(file)}")
    if sum(provided) != 1:
        print(f"[DEBUG /kb/add] ERROR: Invalid source count - {sum(provided)} sources provided")
        raise HTTPException(status_code=400, detail="Provide exactly one of: url, structured_text, file")

    print(f"[DEBUG /kb/add] Checking quota limits...")
    # Check quota limits before processing
    check_files_quota(db, user)
    
    source_uri = None
    s3_original_key = None
    s3_extracted_key = None
    original_filename = None
    file_size_bytes = 0
    extracted_size_bytes = 0
    transient_text = None

    # Handle file upload (PDF/TXT)
    if source_type in (schemas.KBSourceType.upload_pdf, schemas.KBSourceType.upload_txt, schemas.KBSourceType.other):
        if not file:
            raise HTTPException(status_code=400, detail="File is required for upload_* source types")
        
        # Read file content
        file_content = await file.read()
        file_size_bytes = len(file_content)
        
        # Check storage quota
        check_storage_quota(db, user, file_size_bytes)
        
        # Generate KB ID early for S3 path
        kb_id = str(uuid_lib.uuid4())
        original_filename = file.filename
        
        # Upload original file to Cloudflare worker storage
        file_extension = original_filename.split('.')[-1] if '.' in original_filename else 'bin'
        original_upload = await upload_knowledge_file(file_content, original_filename, file.content_type)
        s3_original_key = original_upload.url
        
        extracted_text = extract_text_from_file(file_content, original_filename)
        
        # Upload extracted text to Cloudflare worker storage for reindex/content retrieval
        transient_text = extracted_text
        s3_extracted_key = await try_upload_extracted_text(extracted_text, f"kb_{kb_id}_extracted.txt")
        extracted_size_bytes = len(extracted_text.encode('utf-8'))
        source_uri = original_upload.url
        
    # Handle URL scraping
    elif source_type == schemas.KBSourceType.url:
        if not url:
            raise HTTPException(status_code=400, detail="url is required for source_type=url")
        
        # Scrape URL content
        scraped_data = await scrape_url_content(url)
        extracted_text = scraped_data.get("text", "")
        extracted_size_bytes = len(extracted_text.encode('utf-8'))
        
        # Check storage quota for extracted text
        check_storage_quota(db, user, extracted_size_bytes)
        
        # Generate KB ID for S3 path
        kb_id = str(uuid_lib.uuid4())
        
        # Upload extracted text to Cloudflare worker storage
        transient_text = extracted_text
        s3_extracted_key = await try_upload_extracted_text(extracted_text, f"kb_{kb_id}_extracted.txt")
        
        # Keep metadata inline for now; the worker stores the extracted page text URL.
        source_uri = url
        original_filename = scraped_data.get("title", url)
        
    # Handle structured text
    elif source_type == schemas.KBSourceType.text:
        if not structured_text:
            raise HTTPException(status_code=400, detail="structured_text is required for source_type=text")
        
        extracted_size_bytes = len(structured_text.encode('utf-8'))
        
        # Check storage quota
        check_storage_quota(db, user, extracted_size_bytes)
        
        # Generate KB ID for S3 path
        kb_id = str(uuid_lib.uuid4())
        
        # Upload text to Cloudflare worker storage
        transient_text = structured_text
        s3_extracted_key = await try_upload_extracted_text(structured_text, f"kb_{kb_id}_extracted.txt")
        source_uri = None
        original_filename = title or "Structured Text"
        
    else:
        raise HTTPException(status_code=400, detail="Unsupported source_type")

    # Create KB record with S3 metadata
    kb = models.KnowledgeBase(
        id=kb_id,
        agent_id=agent.id,
        source_type=models.KBSourceType(source_type.value),
        source_uri=source_uri,
        title=title or original_filename,
        status=models.KBStatus.pending,
        s3_original_key=s3_original_key,
        s3_extracted_key=s3_extracted_key,
        original_filename=original_filename,
        file_size_bytes=file_size_bytes,
        extracted_size_bytes=extracted_size_bytes
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    print(f"[DEBUG /kb/add] KB created successfully - kb_id: {kb.id}, agent_id: {agent_id}")

    # Update storage usage (chunk count will be updated by ingest worker)
    increment_storage_usage(db, user.id, file_size_bytes + extracted_size_bytes, 0)

    # Create ingest job
    job = models.KBIngestJob(
        kb_id=kb.id,
        state=models.JobState.queued
    )
    db.add(job)
    db.commit()

    print(f"[DEBUG /kb/add] Ingest job created - job_id: {job.id}")

    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), transient_text)
        print(f"[DEBUG /kb/add] Background task added for job_id: {job.id}")

    print(f"[DEBUG /kb/add] SUCCESS - Returning KB response")
    return kb


@router.get("/{agent_id}", response_model=List[schemas.KnowledgeBaseOut])
def list_kbs(
    agent_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of KBs to return"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.agent_id == agent.id
    ).offset(skip).limit(limit).all()


@router.delete("/{kb_id}")
def delete_kb(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    # Check ownership via agent
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Delete from Qdrant vector store
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_for_kb(cfg.vector_store_namespace, str(kb.id))
        except Exception:
            pass
    
    # Delete from S3
    if (kb.s3_original_key and not str(kb.s3_original_key).startswith(("http://", "https://"))) or (
        kb.s3_extracted_key and not str(kb.s3_extracted_key).startswith(("http://", "https://"))
    ):
        try:
            delete_kb_files(user.id, agent.id, kb.id)
        except Exception:
            pass
    
    # Decrement storage usage
    total_size = (kb.file_size_bytes or 0) + (kb.extracted_size_bytes or 0)
    if total_size > 0:
        decrement_storage_usage(db, user.id, total_size, kb.chunk_count or 0)
    
    db.delete(kb)
    db.commit()
    return {"message": "KB deleted"}


@router.post("/{kb_id}/reindex", response_model=schemas.KBIngestJobOut)
def reindex_kb(kb_id: str, background_tasks: BackgroundTasks = None, db: Session = Depends(get_db), user = Depends(get_current_user)):
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")

    kb.status = models.KBStatus.pending
    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()
    db.refresh(job)
    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), None)
    return job


@router.get("/{kb_id}/content")
async def get_kb_content(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    # Get extracted text content from S3
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    if not kb.s3_extracted_key:
        raise HTTPException(status_code=404, detail="No extracted content available")
    
    try:
        if str(kb.s3_extracted_key).startswith(("http://", "https://")):
            content = await download_text_from_url(kb.s3_extracted_key)
        else:
            content = download_text_from_s3(kb.s3_extracted_key)
        return {
            "kb_id": kb_id,
            "title": kb.title,
            "content": content,
            "source_type": kb.source_type.value,
            "extracted_size_bytes": kb.extracted_size_bytes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")


@router.get("/{kb_id}/download")
def get_kb_download_url(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    # Get presigned URL for original file download
    if not validate_uuid(kb_id):
        raise HTTPException(status_code=400, detail="Invalid KB ID format")
    
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    original_url = kb.source_uri or kb.s3_original_key
    if not original_url:
        raise HTTPException(status_code=404, detail="No original file available for download")
    
    try:
        if str(original_url).startswith(("http://", "https://")):
            presigned_url = original_url
        else:
            presigned_url = get_presigned_url(kb.s3_original_key, kb.original_filename, expiration=3600)
        return {
            "kb_id": kb_id,
            "filename": kb.original_filename,
            "download_url": presigned_url,
            "expires_in_seconds": 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")


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
            "created_at": latest_job.created_at.isoformat() if latest_job.created_at else None
        }
    else:
        response["latest_job"] = None
    
    return response
