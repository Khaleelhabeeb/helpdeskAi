import anyio
import uuid as uuid_lib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from services import cache_keys
from services.ai_prompt_builder import generate_system_prompt_from_text
from services.file_parser import extract_text_from_file
from services.ingest_queue import enqueue_kb_ingest
from services.kb_limits import PayloadTooLargeError, enforce_text_limit, read_upload_limited
from services.redis_client import cache_delete
from services.storage_quota import check_files_quota, check_storage_quota, increment_storage_usage
from utils.jwt import get_current_user

router = APIRouter()


@router.post("/upload")
async def upload_file(
    agent_id: str = Form(...),
    file: UploadFile = File(...),
    legacy_prompt_update: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    filename = file.filename or "upload"

    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == agent_id, models.Agent.user_id == user.id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=403, detail="Agent not found or not yours")

    check_files_quota(db, user)

    try:
        file_content = await read_upload_limited(file)
    except PayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    file_size_bytes = len(file_content)

    check_storage_quota(db, user, file_size_bytes)

    try:
        extracted_text = await anyio.to_thread.run_sync(extract_text_from_file, file_content, filename)
        extracted_size_bytes = enforce_text_limit(extracted_text)
    except PayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if legacy_prompt_update:
        cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
        if cfg and cfg.system_prompt_locked:
            raise HTTPException(
                status_code=400,
                detail="System prompt is locked; cannot overwrite via legacy upload",
            )

        system_prompt = generate_system_prompt_from_text(extracted_text, agent.name)
        agent.instructions = system_prompt
        db.commit()
        return {"message": "Agent instructions updated (legacy)", "system_prompt": system_prompt}

    kb_id = str(uuid_lib.uuid4())

    if filename.lower().endswith(".pdf"):
        source_type = models.KBSourceType.upload_pdf
    elif filename.lower().endswith(".txt"):
        source_type = models.KBSourceType.upload_txt
    else:
        source_type = models.KBSourceType.other

    kb = models.KnowledgeBase(
        id=kb_id,
        agent_id=agent.id,
        source_type=source_type,
        source_uri=filename,
        status=models.KBStatus.pending,
        original_filename=filename,
        file_size_bytes=file_size_bytes,
        extracted_size_bytes=extracted_size_bytes,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    increment_storage_usage(db, user.id, file_size_bytes + extracted_size_bytes, 0)

    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()

    if not enqueue_kb_ingest(str(job.id), extracted_text):
        raise HTTPException(
            status_code=503,
            detail="Knowledge ingestion queue is full. Please try again shortly.",
        )

    cache_delete(cache_keys.dashboard_summary(user.id))
    return {"message": "Knowledge base added and ingest queued", "kb_id": str(kb.id)}
