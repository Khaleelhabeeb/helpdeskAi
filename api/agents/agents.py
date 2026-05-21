from fastapi import UploadFile, File, Form, Query
import logging
from db import models
from services.ai_prompt_builder import default_system_prompt
from db import schemas
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter, HTTPException
from api.auth.auth import get_db
from typing import Optional
from pydantic import BaseModel
from utils.jwt import get_current_user
from uuid import UUID
from services.vector_store import delete_namespace
from services.image_upload import ImageUploadError, upload_avatar_image
from services.kb_source_storage import delete_kb_source
from services.kb_limits import PayloadTooLargeError, read_upload_limited
from services.redis_client import cache_key, redis_delete
from services.chat_runtime import invalidate_agent_runtime
import os

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_AVATAR_BYTES = int(os.getenv("MAX_AVATAR_BYTES", str(2 * 1024 * 1024)))
ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL", "groq/llama-3.1-8b-instant")

@router.post("/create", response_model=schemas.AgentOut)
async def create_agent(
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    enable_retrieval: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Generate default instructions if not provided
    instructions = instructions or default_system_prompt(name)
    
    # Create agent
    new_agent = models.Agent(
        name=name,
        instructions=instructions,
        user_id=user.id,
        model=model or DEFAULT_CHAT_MODEL,
    )
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
    
    db.refresh(new_agent)
    return new_agent


@router.post("/{agent_id}/avatar", response_model=schemas.AgentOut)
async def update_agent_avatar(
    agent_id: UUID,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if avatar.content_type and avatar.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="Avatar must be a PNG, JPEG, WebP, or GIF image")
    try:
        file_bytes = await read_upload_limited(avatar, max_bytes=MAX_AVATAR_BYTES)
    except PayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Avatar file is empty")

    try:
        result = await upload_avatar_image(file_bytes, avatar.filename or "avatar", avatar.content_type)
    except ImageUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent.avatar_url = result.url
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
    if deployment:
        deployment.logo_url = result.url
        redis_delete(cache_key("widget", "config", deployment.deployment_id))
    db.commit()
    db.refresh(agent)
    invalidate_agent_runtime(str(agent.id), agent.user_id)
    return agent


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
    if update.model is not None:
        agent.model = update.model

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.system_prompt_locked and update.instructions is not None:
        raise HTTPException(status_code=400, detail="System prompt is locked; unlock in config to edit instructions")
    if update.instructions is not None:
        agent.instructions = update.instructions
    db.commit()
    db.refresh(agent)
    invalidate_agent_runtime(str(agent.id), agent.user_id)
    return agent

@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, db: Session = Depends(get_db), user = Depends(get_current_user)):
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
    
    # Try to clean vector store
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_namespace(cfg.vector_store_namespace)
        except Exception:
            logger.exception("failed_to_delete_agent_vectors agent_id=%s", agent_id)

    for kb in kbs:
        await delete_kb_source(kb.source_storage_key)
    
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
    invalidate_agent_runtime(str(agent.id), agent.user_id)
    return cfg
