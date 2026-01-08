from fastapi import UploadFile, File, Form, BackgroundTasks
import os
import uuid
from services.file_parser import extract_text_from_pdf_file, extract_text_from_txt_file
from services.ai_prompt_builder import generate_system_prompt_from_text, default_guardrail_system_prompt
from db import models, schemas
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter, HTTPException
from api.auth.auth import get_db
from typing import Optional
from pydantic import BaseModel
from utils.jwt import get_current_user
from uuid import UUID
from services.ingest_worker import process_kb_ingest_job
from services.vector_store import delete_namespace

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/create", response_model=schemas.AgentOut)
async def create_agent_with_upload(
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    structured_text: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    enable_retrieval: bool = Form(True),
    legacy_prompt_update: bool = Form(False),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Check user tier limits
    existing_agents = db.query(models.Agent).filter(models.Agent.user_id == user.id).count()
    if user.user_type == "free" and existing_agents >= 1:
        raise HTTPException(
            status_code=403,
            detail="Free users can only create one agent. Please upgrade to a paid or pro plan for more agents."
        )
    elif user.user_type == "paid" and existing_agents >= 3:
        raise HTTPException(
            status_code=403,
            detail="Paid users can create up to 3 agents. Please upgrade to a pro plan for unlimited agents."
        )

    # only one of file/structured_text/url is provided
    provided_sources = [bool(file), bool(structured_text), bool(url)]
    if sum(provided_sources) != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one knowledge source: file OR structured_text OR url")

    guardrails = instructions or default_guardrail_system_prompt(name)
    new_agent = models.Agent(name=name, instructions=guardrails, user_id=user.id)
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    namespace = f"{user.id}:{new_agent.id}"
    config = models.AgentConfig(
        agent_id=new_agent.id,
        retrieval_enabled=bool(enable_retrieval),
        retrieval_top_k=4,
        embedding_model=None,
        vector_store_namespace=namespace,
        system_prompt_locked=True
    )
    db.add(config)
    db.commit()

    source_type = None
    source_uri = None
    raw_text = None

    if file:
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        if file.filename.lower().endswith(".pdf"):
            source_type = models.KBSourceType.upload_pdf
        elif file.filename.lower().endswith(".txt"):
            source_type = models.KBSourceType.upload_txt
        else:
            source_type = models.KBSourceType.other
        source_uri = file_path
    elif structured_text:
        source_type = models.KBSourceType.text
        raw_text = None
    elif url:
        source_type = models.KBSourceType.url
        source_uri = url

    kb = models.KnowledgeBase(
        agent_id=new_agent.id,
        source_type=source_type,
        source_uri=source_uri,
        status=models.KBStatus.pending
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)

    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()

    transient_text = structured_text if source_type == models.KBSourceType.text else None
    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), transient_text)

    if legacy_prompt_update:
        cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == new_agent.id).first()
        if cfg and cfg.system_prompt_locked:
            raise HTTPException(status_code=400, detail="System prompt is locked; cannot overwrite via legacy path")
        extracted_text = raw_text or ""
        if not extracted_text and source_uri and file:
            try:
                if file.filename.lower().endswith(".pdf"):
                    extracted_text = extract_text_from_pdf_file(open(source_uri, "rb"))
                elif file.filename.lower().endswith(".txt"):
                    extracted_text = extract_text_from_txt_file(open(source_uri, "rb"))
            except Exception:
                pass
        if extracted_text:
            new_agent.instructions = generate_system_prompt_from_text(extracted_text, name)
            db.commit()

    db.refresh(new_agent)
    return new_agent


@router.get("/", response_model=list[schemas.AgentOut])
def get_user_agents(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return db.query(models.Agent).filter(models.Agent.user_id == user.id).all()

@router.put("/{agent_id}/edit", response_model=schemas.AgentOut)
def update_agent(agent_id: UUID, update: schemas.AgentCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.name = update.name

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.system_prompt_locked and update.instructions is not None:
        raise HTTPException(status_code=400, detail="System prompt is locked; unlock in config to edit instructions")
    if update.instructions is not None:
        agent.instructions = update.instructions
    db.commit()
    db.refresh(agent)
    return agent

@router.delete("/{agent_id}")
def delete_agent(agent_id: UUID, db: Session = Depends(get_db), user = Depends(get_current_user)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Try to clean vector store
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_namespace(cfg.vector_store_namespace)
        except Exception:
            pass
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted"}


@router.get("/{agent_id}/config", response_model=schemas.AgentConfigOut)
def get_agent_config(agent_id: UUID, db: Session = Depends(get_db), user = Depends(get_current_user)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if not cfg:

        cfg = models.AgentConfig(agent_id=agent.id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


class AgentConfigUpdate(BaseModel):
    retrieval_enabled: Optional[bool] = None
    retrieval_top_k: Optional[int] = None
    embedding_model: Optional[str] = None
    vector_store_namespace: Optional[str] = None
    system_prompt_locked: Optional[bool] = None


@router.put("/{agent_id}/config", response_model=schemas.AgentConfigOut)
def update_agent_config(agent_id: UUID, update: AgentConfigUpdate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if not cfg:
        cfg = models.AgentConfig(agent_id=agent.id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    # Apply partial updates
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    db.commit()
    db.refresh(cfg)
    return cfg
