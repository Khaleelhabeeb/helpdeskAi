from fastapi import UploadFile, File, Form, BackgroundTasks, Query
import uuid as uuid_lib
from db import models
from services.file_parser import extract_text_from_pdf_file, extract_text_from_txt_file, extract_text_from_pdf, extract_text_from_txt
from services.ai_prompt_builder import generate_system_prompt_from_text, default_guardrail_system_prompt
from db import schemas
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter, HTTPException
from api.auth.auth import get_db
from typing import Optional
from pydantic import BaseModel
from utils.jwt import get_current_user
from uuid import UUID
from services.ingest_worker import process_kb_ingest_job
from services.vector_store import delete_namespace
from services.s3_storage import upload_file_to_s3, upload_text_to_s3, delete_kb_files, get_s3_key
from services.storage_quota import check_storage_quota, check_files_quota, increment_storage_usage
from api.scrape.scrape import scrape_url_content
import json

router = APIRouter()

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

    # Check quota limits before creating agent
    check_files_quota(db, user)

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
    s3_original_key = None
    s3_extracted_key = None
    original_filename = None
    file_size_bytes = 0
    extracted_size_bytes = 0

    # Generate KB ID early for S3 path
    kb_id = str(uuid_lib.uuid4())

    # Handle file upload (PDF/TXT)
    if file:
        file_content = await file.read()
        file_size_bytes = len(file_content)
        
        # Check storage quota
        check_storage_quota(db, user, file_size_bytes)
        
        original_filename = file.filename
        
        # Determine source type
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
        s3_original_key = get_s3_key(user.id, str(new_agent.id), str(kb_id), "original", file_extension)
        upload_file_to_s3(file_content, s3_original_key)
        
        # Extract text
        if source_type == models.KBSourceType.upload_pdf:
            extracted_text = extract_text_from_pdf(file_content)
        elif source_type == models.KBSourceType.upload_txt:
            extracted_text = extract_text_from_txt(file_content)
        else:
            extracted_text = ""
        
        # Upload extracted text to S3
        if extracted_text:
            s3_extracted_key = get_s3_key(user.id, str(new_agent.id), str(kb_id), "extracted", "txt")
            upload_text_to_s3(extracted_text, s3_extracted_key)
            extracted_size_bytes = len(extracted_text.encode('utf-8'))
        
        source_uri = s3_original_key
        
    # Handle structured text
    elif structured_text:
        source_type = models.KBSourceType.text
        extracted_text = structured_text
        extracted_size_bytes = len(structured_text.encode('utf-8'))
        
        # Check storage quota
        check_storage_quota(db, user, extracted_size_bytes)
        
        # Upload text to S3
        s3_extracted_key = get_s3_key(user.id, str(new_agent.id), str(kb_id), "extracted", "txt")
        upload_text_to_s3(structured_text, s3_extracted_key)
        source_uri = None
        original_filename = "Structured Text"
        
    # Handle URL scraping
    elif url:
        source_type = models.KBSourceType.url
        
        # Scrape URL content
        scraped_data = await scrape_url_content(url)
        extracted_text = scraped_data.get("text", "")
        extracted_size_bytes = len(extracted_text.encode('utf-8'))
        
        # Check storage quota
        check_storage_quota(db, user, extracted_size_bytes)
        
        # Upload extracted text to S3
        s3_extracted_key = get_s3_key(user.id, str(new_agent.id), str(kb_id), "extracted", "txt")
        upload_text_to_s3(extracted_text, s3_extracted_key)
        
        # Save metadata as JSON
        metadata_json = json.dumps({
            "url": url,
            "title": scraped_data.get("title", ""),
            "scraped_at": scraped_data.get("timestamp")
        })
        metadata_key = get_s3_key(user.id, str(new_agent.id), str(kb_id), "metadata", "json")
        upload_text_to_s3(metadata_json, metadata_key)
        
        source_uri = url
        original_filename = scraped_data.get("title", url)

    # Create KB record with S3 metadata
    kb = models.KnowledgeBase(
        id=kb_id,
        agent_id=new_agent.id,
        source_type=source_type,
        source_uri=source_uri,
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

    # Update storage usage
    increment_storage_usage(db, user.id, file_size_bytes + extracted_size_bytes, 0)

    job = models.KBIngestJob(kb_id=kb.id, state=models.JobState.queued)
    db.add(job)
    db.commit()

    if background_tasks is not None:
        background_tasks.add_task(process_kb_ingest_job, str(job.id), None)

    if legacy_prompt_update:
        cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == new_agent.id).first()
        if cfg and cfg.system_prompt_locked:
            raise HTTPException(status_code=400, detail="System prompt is locked; cannot overwrite via legacy path")
        
        # Use extracted_text from above (already available)
        if extracted_text:
            new_agent.instructions = generate_system_prompt_from_text(extracted_text, name)
            db.commit()

    db.refresh(new_agent)
    return new_agent


@router.get("/", response_model=list[schemas.AgentOut])
def get_user_agents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of agents to return"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    return db.query(models.Agent).filter(
        models.Agent.user_id == user.id
    ).offset(skip).limit(limit).all()

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
    
    # Get all KBs for this agent
    kbs = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.agent_id == agent.id).all()
    
    # Calculate total storage to decrement in one go
    total_storage_bytes = 0
    total_chunks = 0
    for kb in kbs:
        total_storage_bytes += (kb.file_size_bytes or 0) + (kb.extracted_size_bytes or 0)
        total_chunks += (kb.chunk_count or 0)
    
    if total_storage_bytes > 0:
        from services.storage_quota import decrement_storage_usage
        decrement_storage_usage(db, user.id, total_storage_bytes, total_chunks)
    
    # Delete S3 files for each KB
    for kb in kbs:
        if kb.s3_original_key or kb.s3_extracted_key:
            try:
                delete_kb_files(user.id, agent.id, kb.id)
            except Exception:
                pass
    
    # Try to clean vector store
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_namespace(cfg.vector_store_namespace)
        except Exception:
            pass
    
    db.delete(agent)
    db.commit()
    return {"message": "Agent and all associated data deleted successfully"}


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
