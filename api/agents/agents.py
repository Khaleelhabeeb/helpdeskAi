from fastapi import UploadFile, File, Form, Query
import logging
import mimetypes
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
from services.image_upload import ImageUploadError, upload_avatar_image, upload_worker_file
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

async def _try_assign_favicon_to_agent(agent: models.Agent, db: Session, favicon_url: Optional[str]) -> Optional[str]:
    """Try to download favicon and upload via image worker, fallback to direct URL.
    Returns the final url assigned or None.
    """
    if not favicon_url or agent.avatar_url:
        return None
    try:
        from services.web_scraper import download_image_bytes, is_safe_url
        if not await is_safe_url(favicon_url):
            return None
        try:
            img_bytes, content_type = await download_image_bytes(favicon_url)
        except Exception as exc:
            logger.info("favicon_download_failed agent_id=%s url=%s err=%s", agent.id, favicon_url, exc)
            # fallback to direct favicon URL if download fails but it's still a valid http URL
            agent.avatar_url = favicon_url
            db.commit()
            db.refresh(agent)
            deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
            if deployment:
                deployment.logo_url = favicon_url
                redis_delete(cache_key("widget", "config", deployment.deployment_id))
                db.commit()
            return favicon_url

        parsed = favicon_url.split("?")[0].split("/")[-1] or "favicon"
        ext = mimetypes.guess_extension(content_type or "") or ".png"
        if "." not in parsed:
            parsed = f"favicon{ext}"
        # Try to upload via image worker if configured, otherwise store direct URL
        worker_configured = bool(os.getenv("IMAGE_WORKER_URL") and os.getenv("IMAGE_WORKER_API_KEY"))
        if worker_configured:
            try:
                result = await upload_avatar_image(img_bytes, parsed, content_type or "image/png")
                final_url = result.url
            except ImageUploadError as exc:
                logger.info("favicon_upload_failed fallback_to_direct agent_id=%s err=%s", agent.id, exc)
                final_url = favicon_url
        else:
            final_url = favicon_url

        agent.avatar_url = final_url
        db.commit()
        db.refresh(agent)
        deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
        if deployment:
            deployment.logo_url = final_url
            redis_delete(cache_key("widget", "config", deployment.deployment_id))
            db.commit()
        else:
            # Create deployment eagerly so widget shows logo immediately
            from models.widget_deployment import new_deployment_id
            from datetime import datetime, timezone
            deployment = models.WidgetDeployment(
                agent_id=agent.id,
                deployment_id=new_deployment_id(),
                display_name=agent.name,
                logo_url=final_url,
                initial_messages=["Hi! What can I help you with?"],
                theme="dark",
                primary_color="#ffffff",
                allowed_domains=["localhost", "127.0.0.1"],
                is_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(deployment)
            db.commit()
        return final_url
    except Exception as exc:
        logger.warning("favicon_assign_failed agent_id=%s err=%s", agent.id, exc, exc_info=True)
        return None


@router.post("/create", response_model=schemas.AgentOut)
async def create_agent(
    name: str = Form(...),
    model: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    avatar_url: Optional[str] = Form(None),
    website_url: Optional[str] = Form(None),
    enable_retrieval: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    instructions = default_system_prompt(name)
    
    new_agent = models.Agent(
        name=name,
        instructions=instructions,
        user_id=user.id,
        model=model or DEFAULT_CHAT_MODEL,
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    # Handle avatar upload if provided
    if avatar and getattr(avatar, "filename", None):
        try:
            if avatar.content_type and avatar.content_type not in ALLOWED_AVATAR_TYPES:
                logger.warning("create_agent_avatar_invalid_type agent_id=%s content_type=%s", new_agent.id, avatar.content_type)
            else:
                file_bytes = await read_upload_limited(avatar, max_bytes=MAX_AVATAR_BYTES)
                if file_bytes:
                    result = await upload_avatar_image(file_bytes, avatar.filename or "avatar", avatar.content_type)
                    new_agent.avatar_url = result.url
                    db.commit()
                    db.refresh(new_agent)
        except Exception as exc:
            logger.warning("create_agent_avatar_upload_failed agent_id=%s err=%s", new_agent.id, exc)

    # Pre-fetch branding if website_url provided (used for favicon + theme color)
    branding: Optional[dict] = None
    if website_url and website_url.strip():
        try:
            from services.web_scraper import scrape_url_branding
            branding = await scrape_url_branding(website_url.strip())
        except Exception as exc:
            logger.info("create_agent_branding_fetch_failed website=%s err=%s", website_url, exc)
            branding = None

    # If no avatar yet, try avatar_url or website favicon
    if not new_agent.avatar_url:
        if avatar_url and avatar_url.strip():
            await _try_assign_favicon_to_agent(new_agent, db, avatar_url.strip())
        elif branding:
            favicon_candidate = branding.get("logo_url") or branding.get("favicon_url") or branding.get("og_image_url")
            if favicon_candidate:
                await _try_assign_favicon_to_agent(new_agent, db, favicon_candidate)

    namespace = f"{user.id}:{new_agent.id}"
    config = models.AgentConfig(
        agent_id=new_agent.id,
        retrieval_enabled=bool(enable_retrieval),
        retrieval_top_k=4,
        embedding_model=None,
        vector_store_namespace=namespace,
        system_prompt_locked=False  # Allow editing initially
    )
    # Propagate theme color from branding to widget_color if valid
    if branding:
        theme_color = branding.get("theme_color")
        if theme_color and isinstance(theme_color, str) and theme_color.startswith("#") and len(theme_color) == 7:
            try:
                int(theme_color[1:], 16)
                config.widget_color = theme_color
                config.widget_use_color_header = True
            except Exception:
                pass
    db.add(config)
    db.commit()

    # Ensure widget deployment reflects avatar/logo and theme color
    theme_color_to_use = "#ffffff"
    if branding:
        tc = branding.get("theme_color")
        if tc and isinstance(tc, str) and tc.startswith("#") and len(tc) == 7:
            try:
                int(tc[1:], 16)
                theme_color_to_use = tc
            except Exception:
                pass
    if new_agent.avatar_url:
        deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == new_agent.id).first()
        if not deployment:
            from models.widget_deployment import new_deployment_id
            from datetime import datetime, timezone
            deployment = models.WidgetDeployment(
                agent_id=new_agent.id,
                deployment_id=new_deployment_id(),
                display_name=new_agent.name,
                logo_url=new_agent.avatar_url,
                initial_messages=["Hi! What can I help you with?"],
                theme="dark",
                primary_color=theme_color_to_use,
                allowed_domains=["localhost", "127.0.0.1"],
                is_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(deployment)
            db.commit()
        else:
            # Sync logo if missing
            if not deployment.logo_url and new_agent.avatar_url:
                deployment.logo_url = new_agent.avatar_url
                # sync color if deployment still default white and we have branded color
                if deployment.primary_color == "#ffffff" and theme_color_to_use != "#ffffff":
                    deployment.primary_color = theme_color_to_use
                db.commit()
    elif branding and theme_color_to_use != "#ffffff":
        # No avatar but we have theme color -> create deployment with that color
        deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == new_agent.id).first()
        if not deployment:
            from models.widget_deployment import new_deployment_id
            from datetime import datetime, timezone
            deployment = models.WidgetDeployment(
                agent_id=new_agent.id,
                deployment_id=new_deployment_id(),
                display_name=new_agent.name,
                logo_url=None,
                initial_messages=["Hi! What can I help you with?"],
                theme="dark",
                primary_color=theme_color_to_use,
                allowed_domains=["localhost", "127.0.0.1"],
                is_enabled=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(deployment)
            db.commit()
        elif deployment.primary_color == "#ffffff":
            deployment.primary_color = theme_color_to_use
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
    
    kbs = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.agent_id == agent.id).all()
    
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
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    db.commit()
    db.refresh(cfg)
    invalidate_agent_runtime(str(agent.id), agent.user_id)
    return cfg
