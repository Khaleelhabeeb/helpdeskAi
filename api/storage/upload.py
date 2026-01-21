from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
import uuid as uuid_lib
from services.file_parser import extract_text_from_pdf, extract_text_from_txt
from services.ai_prompt_builder import generate_system_prompt_from_text
from api.auth.auth import get_db
from db import models
from sqlalchemy.orm import Session
from utils.jwt import get_current_user
from services.ingest_worker import process_kb_ingest_job
from services.s3_storage import upload_file_to_s3, upload_text_to_s3, get_s3_key
from services.storage_quota import check_storage_quota, check_files_quota, increment_storage_usage

router = APIRouter()

@router.post("/upload")
async def upload_file(agent_id: str = Form(...), file: UploadFile = File(...), legacy_prompt_update: bool = Form(False),
                background_tasks: BackgroundTasks = None,
                db: Session = Depends(get_db), user=Depends(get_current_user)):

    # Check agent ownership
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Agent not found or not yours")

    # Check quota limits
    check_files_quota(db, user)

    # Read file content
    file_content = await file.read()
    file_size_bytes = len(file_content)
    
    # Check storage quota
    check_storage_quota(db, user, file_size_bytes)

    # Extract text from file
    if file.filename.endswith(".pdf"):
        extracted_text = extract_text_from_pdf(file_content)
    elif file.filename.endswith(".txt"):
        extracted_text = extract_text_from_txt(file_content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format")

    if legacy_prompt_update:
        cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
        if cfg and cfg.system_prompt_locked:
            raise HTTPException(status_code=400, detail="System prompt is locked; cannot overwrite via legacy upload")

        system_prompt = generate_system_prompt_from_text(extracted_text, agent.name)
        agent.instructions = system_prompt
        db.commit()
        return {"message": "Agent instructions updated (legacy)", "system_prompt": system_prompt}

    # Generate KB ID for S3 path
    kb_id = str(uuid_lib.uuid4())
    
    # Determine source type and file extension
    if file.filename.lower().endswith(".pdf"):
        source_type = models.KBSourceType.upload_pdf
        file_extension = "pdf"
    elif file.filename.lower().endswith(".txt"):
        source_type = models.KBSourceType.upload_txt
        file_extension = "txt"
    else:
        source_type = models.KBSourceType.other
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
    
    # Upload original file to S3
    s3_original_key = get_s3_key(user.id, str(agent.id), kb_id, "original", file_extension)
    upload_file_to_s3(file_content, s3_original_key)
    
    # Upload extracted text to S3
    s3_extracted_key = get_s3_key(user.id, str(agent.id), kb_id, "extracted", "txt")
    upload_text_to_s3(extracted_text, s3_extracted_key)
    extracted_size_bytes = len(extracted_text.encode('utf-8'))

    # Create KB record with S3 metadata
    kb = models.KnowledgeBase(
        id=kb_id,
        agent_id=agent.id,
        source_type=source_type,
        source_uri=s3_original_key,
        status=models.KBStatus.pending,
        s3_original_key=s3_original_key,
        s3_extracted_key=s3_extracted_key,
        original_filename=file.filename,
        file_size_bytes=file_size_bytes,
        extracted_size_bytes=extracted_size_bytes
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    
    # Update storage usage
    increment_storage_usage(db, user.id, file_size_bytes + extracted_size_bytes, 0)

    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()

    # Schedule background ingest (scaffold only)
    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), None)

    return {"message": "Knowledge base added and ingest queued", "kb_id": str(kb.id)}
