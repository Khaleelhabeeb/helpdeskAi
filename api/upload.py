from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
import os
import uuid
from services.file_parser import extract_text_from_pdf_file, extract_text_from_txt_file
from services.ai_prompt_builder import generate_system_prompt_from_text
from api.auth import get_db
from db import models
from sqlalchemy.orm import Session
from utils.jwt import get_current_user
from services.ingest_worker import process_kb_ingest_job

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
def upload_file(agent_id: str = Form(...), file: UploadFile = File(...), legacy_prompt_update: bool = Form(False),
                background_tasks: BackgroundTasks = None,
                db: Session = Depends(get_db), user=Depends(get_current_user)):

    # Check agent ownership
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=403, detail="Agent not found or not yours")

    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    if file.filename.endswith(".pdf"):
        with open(file_path, "rb") as rf:
            extracted_text = extract_text_from_pdf_file(rf)
    elif file.filename.endswith(".txt"):
        with open(file_path, "rb") as rf:
            extracted_text = extract_text_from_txt_file(rf)
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

    if file.filename.lower().endswith(".pdf"):
        source_type = models.KBSourceType.upload_pdf
    elif file.filename.lower().endswith(".txt"):
        source_type = models.KBSourceType.upload_txt
    else:
        source_type = models.KBSourceType.other

    kb = models.KnowledgeBase(
        agent_id=agent.id,
        source_type=source_type,
        source_uri=file_path,
        status=models.KBStatus.pending
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()

    # Schedule background ingest (scaffold only)
    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), None)

    return {"message": "Knowledge base added and ingest queued", "kb_id": str(kb.id)}
