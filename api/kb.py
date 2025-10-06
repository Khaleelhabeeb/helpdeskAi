from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import Optional, List
from sqlalchemy.orm import Session
from db import models, schemas
from api.auth import get_db
from utils.jwt import get_current_user
import os
import uuid
from services.ingest_worker import process_kb_ingest_job
from services.vector_store import delete_for_kb

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/add", response_model=schemas.KnowledgeBaseOut)
def add_knowledge_base(
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
        raise HTTPException(status_code=404, detail="Agent not found")

    provided = [bool(url), bool(structured_text), bool(file)]
    if sum(provided) != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one of: url, structured_text, file")

    source_uri = None
    raw_text = None

    if source_type in (schemas.KBSourceType.upload_pdf, schemas.KBSourceType.upload_txt):
        if not file:
            raise HTTPException(status_code=400, detail="File is required for upload_* source types")
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        source_uri = file_path
    elif source_type == schemas.KBSourceType.url:
        if not url:
            raise HTTPException(status_code=400, detail="url is required for source_type=url")
        source_uri = url
    elif source_type == schemas.KBSourceType.text:
        if not structured_text:
            raise HTTPException(status_code=400, detail="structured_text is required for source_type=text")
        raw_text = None
    else:
        raise HTTPException(status_code=400, detail="Unsupported source_type")

    kb = models.KnowledgeBase(
        agent_id=agent.id,
        source_type=models.KBSourceType(source_type.value),
        source_uri=source_uri,
    title=title,
        status=models.KBStatus.pending
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    # Create ingest job (queued)
    job = models.KBIngestJob(
        kb_id=kb.id,
        state=models.JobState.queued
    )
    db.add(job)
    db.commit()

    transient_text = structured_text if source_type == schemas.KBSourceType.text else None
    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), transient_text)

    return kb


@router.get("/{agent_id}", response_model=List[schemas.KnowledgeBaseOut])
def list_kbs(agent_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db.query(models.KnowledgeBase).filter(models.KnowledgeBase.agent_id == agent.id).all()


@router.delete("/{kb_id}")
def delete_kb(kb_id: str, db: Session = Depends(get_db), user = Depends(get_current_user)):
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == kb_id).first()
    if not kb:
        raise HTTPException(status_code=404, detail="KB not found")
    # Check ownership via agent
    agent = db.query(models.Agent).filter(models.Agent.id == kb.agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Forbidden")

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_for_kb(cfg.vector_store_namespace, str(kb.id))
        except Exception:
            pass
    db.delete(kb)
    db.commit()
    return {"message": "KB deleted"}


@router.post("/{kb_id}/reindex", response_model=schemas.KBIngestJobOut)
def reindex_kb(kb_id: str, background_tasks: BackgroundTasks = None, db: Session = Depends(get_db), user = Depends(get_current_user)):
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
