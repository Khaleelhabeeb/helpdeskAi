import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models, schemas
from services import cache_keys
from services.ai_prompt_builder import default_system_prompt
from services.image_upload import ImageUploadError, upload_avatar_image
from services.kb_limits import PayloadTooLargeError, read_upload_limited
from services.redis_client import cache_delete
from services.vector_store import delete_namespace
from utils.jwt import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)

MAX_AVATAR_UPLOAD_BYTES = 2 * 1024 * 1024


@router.post("/create", response_model=schemas.AgentOut)
async def create_agent(
    name: str = Form(...),
    instructions: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    enable_retrieval: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    instructions = instructions or default_system_prompt(name)

    new_agent = models.Agent(
        name=name,
        instructions=instructions,
        user_id=user.id,
        model=model or "groq/openai/gpt-oss-20b",
    )
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
        system_prompt_locked=False,
    )
    db.add(config)
    db.commit()

    db.refresh(new_agent)
    cache_delete(cache_keys.dashboard_summary(user.id))
    return new_agent


@router.post("/{agent_id}/avatar", response_model=schemas.AgentOut)
async def update_agent_avatar(
    agent_id: UUID,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        file_bytes = await read_upload_limited(avatar, max_bytes=MAX_AVATAR_UPLOAD_BYTES)
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
        cache_delete(cache_keys.widget_config(deployment.deployment_id))

    db.commit()
    db.refresh(agent)
    cache_delete(cache_keys.agent_runtime(agent.id))
    return agent


@router.get("/", response_model=list[schemas.AgentOut])
def get_user_agents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max number of agents to return"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return (
        db.query(models.Agent)
        .filter(models.Agent.user_id == user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.put("/{agent_id}/edit", response_model=schemas.AgentOut)
def update_agent(
    agent_id: UUID,
    update: schemas.AgentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
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
    cache_delete(cache_keys.agent_runtime(agent.id))
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    kbs = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.agent_id == agent.id).all()

    total_storage_bytes = 0
    total_chunks = 0
    for kb in kbs:
        total_storage_bytes += (kb.file_size_bytes or 0) + (kb.extracted_size_bytes or 0)
        total_chunks += kb.chunk_count or 0

    if total_storage_bytes > 0:
        from services.storage_quota import decrement_storage_usage

        decrement_storage_usage(db, user.id, total_storage_bytes, total_chunks)

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if cfg and cfg.vector_store_namespace:
        try:
            delete_namespace(cfg.vector_store_namespace)
        except Exception:
            logger.exception("failed_to_delete_agent_vectors agent_id=%s", agent_id)

    db.delete(agent)
    db.commit()
    cache_delete(cache_keys.agent_runtime(agent_id))
    cache_delete(cache_keys.dashboard_summary(user.id))
    return {"message": "Agent and all associated data deleted successfully"}


@router.get("/{agent_id}/config", response_model=schemas.AgentConfigOut)
def get_agent_config(agent_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
def update_agent_config(
    agent_id: UUID,
    update: AgentConfigUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    if not cfg:
        cfg = models.AgentConfig(agent_id=agent.id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)

    db.commit()
    db.refresh(cfg)
    cache_delete(cache_keys.agent_runtime(agent.id))
    return cfg
