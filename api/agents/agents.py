from fastapi import UploadFile, File, Form, BackgroundTasks, Query
import uuid as uuid_lib
from db import models
from services.file_parser import extract_text_from_pdf_file, extract_text_from_txt_file, extract_text_from_pdf, extract_text_from_txt
from services.ai_prompt_builder import default_system_prompt
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
async def create_agent(
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    enable_retrieval: bool = Form(True),
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

    # Generate default instructions if not provided
    instructions = instructions or default_system_prompt(name)
    
    # Create agent
    new_agent = models.Agent(name=name, instructions=instructions, user_id=user.id)
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    # Create agent configuration
    namespace = f"{user.id}:{new_agent.id}"
    config = models.AgentConfig(
        agent_id=new_agent.id,
        retrieval_enabled=bool(enable_retrieval),
        retrieval_top_k=4,
        embedding_model=None,
        vector_store_namespace=namespace,
        system_prompt_locked=False  # Allow editing initially
    )
    db.add(config)
    db.commit()
    
    # Handle avatar upload if provided
    if avatar:
        avatar_content = await avatar.read()
        avatar_size = len(avatar_content)
        
        # Validate image size (max 5MB)
        if avatar_size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Avatar image must be less than 5MB")
        
        # Validate image type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if avatar.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Avatar must be JPG, PNG, or WebP format")
        
        # Upload avatar to S3
        avatar_extension = avatar.filename.split('.')[-1] if '.' in avatar.filename else 'jpg'
        avatar_key = f"user_{user.id}/agent_{new_agent.id}/avatar.{avatar_extension}"
        upload_file_to_s3(avatar_content, avatar_key, content_type=avatar.content_type)
        
        # Update agent with avatar URL/key
        new_agent.avatar_url = avatar_key
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
