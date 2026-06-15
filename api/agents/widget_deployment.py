import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from api.auth.auth import get_db
from db import models
from db.database import BackgroundSession
from models.widget_deployment import new_deployment_id
from services.redis_client import (
    cache_key,
    get_async_redis,
    redis_delete,
    redis_get_json,
    redis_set_json,
)
from services.rag_service import build_messages, aretrieve_context, astream_answer
from utils.jwt import get_current_user
from utils.widget_security import (
    generate_widget_token,
    get_rate_limit_key,
    detect_abuse_signature,
)

router = APIRouter()
public_router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_INITIAL_MESSAGES = ["Hi! What can I help you with?"]
DEFAULT_ALLOWED_DOMAINS = ["localhost", "127.0.0.1"]
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30
WIDGET_CONFIG_CACHE_TTL_SECONDS = 300
FALLBACK_RATE_LIMIT_MAX_KEYS = 1000
CHAT_RETRIEVAL_TOP_K_CAP = int(os.getenv("CHAT_RETRIEVAL_TOP_K_CAP", "3"))

class WidgetDeploymentUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=120)
    logo_url: Optional[str] = Field(None, max_length=1000)
    initial_messages: Optional[list[str]] = None
    theme: Optional[str] = Field(None, pattern="^(light|dark)$")
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    allowed_domains: Optional[list[str]] = None
    is_enabled: Optional[bool] = None


class PublicChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    visitor_id: Optional[str] = Field(None, max_length=120)
    identity: Optional[dict] = None
    context: Optional[dict] = None


class TelemetryEvent(BaseModel):
    event: str = Field(..., min_length=1, max_length=100)
    data: dict = Field(default_factory=dict)
    timestamp: Optional[int] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _clean_messages(messages: Optional[list[str]]) -> list[str]:
    cleaned = [(message or "").strip() for message in messages or []]
    cleaned = [message for message in cleaned if message]
    return cleaned[:5] or DEFAULT_INITIAL_MESSAGES


def _clean_domain(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _clean_domains(domains: Optional[list[str]]) -> list[str]:
    values = []
    for domain in domains or []:
        cleaned = _clean_domain(domain)
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return values[:25]


def _origin_host(request: Request) -> str:
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if not origin:
        return ""
    parsed = urlparse(origin if "://" in origin else f"https://{origin}")
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _host_allowed(host: str, allowed_domains: list[str]) -> bool:
    if not host:
        return False
    allowed = [_clean_domain(domain) for domain in allowed_domains if _clean_domain(domain)]
    if not allowed:
        return False
    for domain in allowed:
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False


def _origin_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin")
    if not origin:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Vary": "Origin",
    }


def _visitor_hash(deployment_id: int, visitor_id: str, request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    value = f"{deployment_id}:{visitor_id}:{ip}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# High-performance Sliding Window Counter Rate Limiter
_rate_limit_lock = threading.Lock()
_rate_limit_data = {
    "current_window": {},
    "previous_window": {},
    "last_window_start": 0
}


async def _check_rate_limit(deployment_public_id: str, visitor_id: str, request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    redis_client = get_async_redis()
    redis_key = cache_key(
        "ratelimit",
        "widget",
        get_rate_limit_key(deployment_public_id, visitor_id, ip, user_agent),
    )
    if redis_client:
        try:
            count = await redis_client.incr(redis_key)
            if count == 1:
                await redis_client.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS)
            if count > RATE_LIMIT_MAX_REQUESTS:
                logger.warning("rate_limit_exceeded deployment_id=%s ip=%s", deployment_public_id, ip)
                raise HTTPException(status_code=429, detail="Too many messages. Please wait a moment.")
            return
        except HTTPException:
            raise
        except Exception:
            logger.warning("redis_rate_limit_failed deployment_id=%s", deployment_public_id, exc_info=True)

    now = time.time()
    # Calculate the start of the current 60-second window
    window_start = int(now / RATE_LIMIT_WINDOW_SECONDS) * RATE_LIMIT_WINDOW_SECONDS
    
    with _rate_limit_lock:
        if window_start > _rate_limit_data["last_window_start"]:
            # Rotate windows
            if window_start > _rate_limit_data["last_window_start"] + RATE_LIMIT_WINDOW_SECONDS:
                _rate_limit_data["previous_window"] = {}
            else:
                _rate_limit_data["previous_window"] = _rate_limit_data["current_window"]
            _rate_limit_data["current_window"] = {}
            _rate_limit_data["last_window_start"] = window_start
            # Trim previous_window so total memory never exceeds 2x max
            stale = len(_rate_limit_data["previous_window"]) - FALLBACK_RATE_LIMIT_MAX_KEYS
            if stale > 0:
                for _ in range(stale):
                    _rate_limit_data["previous_window"].pop(next(iter(_rate_limit_data["previous_window"])), None)

        key = f"{deployment_public_id}:{ip}"

        current_count = _rate_limit_data["current_window"].get(key, 0)
        prev_count = _rate_limit_data["previous_window"].get(key, 0)

        elapsed = now - window_start
        weight = (RATE_LIMIT_WINDOW_SECONDS - elapsed) / RATE_LIMIT_WINDOW_SECONDS

        estimated_count = current_count + (prev_count * weight)

        if estimated_count >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning("rate_limit_exceeded key=%s ip=%s", key, ip)
            raise HTTPException(status_code=429, detail="Too many messages. Please wait a moment.")

        _rate_limit_data["current_window"][key] = current_count + 1
        if len(_rate_limit_data["current_window"]) > FALLBACK_RATE_LIMIT_MAX_KEYS:
            # Evict 10% at once to avoid O(n) pops under sustained load
            excess = len(_rate_limit_data["current_window"]) - FALLBACK_RATE_LIMIT_MAX_KEYS
            for _ in range(min(excess, FALLBACK_RATE_LIMIT_MAX_KEYS // 10)):
                _rate_limit_data["current_window"].pop(next(iter(_rate_limit_data["current_window"])), None)


def _deployment_out(deployment: models.WidgetDeployment, request: Request) -> dict:
    base_url = str(request.base_url).rstrip("/")
    embed_script = (
        f'<script src="{base_url}/static/widget.js" '
        f'data-deployment-id="{deployment.deployment_id}" defer></script>'
    )
    return {
        "deployment_id": deployment.deployment_id,
        "display_name": deployment.display_name,
        "logo_url": deployment.logo_url or "",
        "initial_messages": deployment.initial_messages or DEFAULT_INITIAL_MESSAGES,
        "theme": deployment.theme,
        "primary_color": deployment.primary_color,
        "allowed_domains": deployment.allowed_domains or [],
        "is_enabled": deployment.is_enabled,
        "embed_script": embed_script,
    }


def _widget_config_cache_key(deployment_id: str) -> str:
    return cache_key("widget", "config", deployment_id)


def invalidate_widget_config_cache(deployment_id: str) -> None:
    redis_delete(_widget_config_cache_key(deployment_id))


def _public_widget_config_payload(db: Session, deployment_id: str) -> Optional[dict]:
    cache_id = _widget_config_cache_key(deployment_id)
    cached = redis_get_json(cache_id)
    if isinstance(cached, dict):
        return cached

    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.deployment_id == deployment_id).first()
    if not deployment or not deployment.is_enabled:
        return None

    updated_at = deployment.updated_at or datetime.now(timezone.utc)
    payload = {
        "deployment_id": deployment.deployment_id,
        "display_name": deployment.display_name,
        "logo_url": deployment.logo_url or "",
        "initial_messages": deployment.initial_messages or DEFAULT_INITIAL_MESSAGES,
        "theme": deployment.theme,
        "primary_color": deployment.primary_color,
        "allowed_domains": deployment.allowed_domains or [],
        "etag": f'W/"{int(updated_at.timestamp())}"',
    }
    redis_set_json(cache_id, payload, WIDGET_CONFIG_CACHE_TTL_SECONDS)
    return payload


def _get_or_create_deployment(db: Session, agent: models.Agent) -> models.WidgetDeployment:
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.agent_id == agent.id).first()
    if deployment:
        return deployment
    deployment = models.WidgetDeployment(
        agent_id=agent.id,
        deployment_id=new_deployment_id(),
        display_name=agent.name,
        logo_url=agent.avatar_url,
        initial_messages=DEFAULT_INITIAL_MESSAGES,
        theme="dark",
        primary_color="#ffffff",
        allowed_domains=DEFAULT_ALLOWED_DOMAINS,
        is_enabled=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


def _history_for_prompt(db: Session, session_id: uuid.UUID, max_messages: int = 8, max_chars: int = 3000) -> list[dict[str, str]]:
    rows = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at.desc())
        .limit(max_messages)
        .all()
    )
    history: list[dict[str, str]] = []
    total = 0
    for row in reversed(rows):
        if row.role not in {"user", "assistant"}:
            continue
        content = row.content.strip()
        if not content:
            continue
        if total + len(content) > max_chars:
            break
        history.append({"role": row.role, "content": content})
        total += len(content)
    return history


@router.get("/{agent_id}/widget-deployment")
def get_widget_deployment(
    agent_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    deployment = _get_or_create_deployment(db, agent)
    return _deployment_out(deployment, request)


@router.patch("/{agent_id}/widget-deployment")
def update_widget_deployment(
    agent_id: uuid.UUID,
    payload: WidgetDeploymentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    deployment = _get_or_create_deployment(db, agent)
    if payload.display_name is not None:
        deployment.display_name = payload.display_name.strip()
    if payload.logo_url is not None:
        deployment.logo_url = payload.logo_url.strip() or None
    if payload.initial_messages is not None:
        deployment.initial_messages = _clean_messages(payload.initial_messages)
    if payload.theme is not None:
        deployment.theme = payload.theme
    if payload.primary_color is not None:
        deployment.primary_color = payload.primary_color
    if payload.allowed_domains is not None:
        deployment.allowed_domains = _clean_domains(payload.allowed_domains)
    if payload.is_enabled is not None:
        deployment.is_enabled = payload.is_enabled
    deployment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deployment)
    invalidate_widget_config_cache(deployment.deployment_id)
    return _deployment_out(deployment, request)


@router.post("/{agent_id}/widget-deployment/regenerate")
def regenerate_widget_deployment(
    agent_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    deployment = _get_or_create_deployment(db, agent)
    old_deployment_id = deployment.deployment_id
    deployment.deployment_id = new_deployment_id()
    deployment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deployment)
    invalidate_widget_config_cache(old_deployment_id)
    invalidate_widget_config_cache(deployment.deployment_id)
    return _deployment_out(deployment, request)


@router.post("/{agent_id}/widget-deployment/token")
def generate_deployment_token(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Generate a signed token for enhanced security (optional)"""
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    deployment = _get_or_create_deployment(db, agent)
    token = generate_widget_token(deployment.deployment_id)
    return {"token": token, "expires_in": 300}


@public_router.get("/{deployment_id}/config")
def get_public_widget_config(deployment_id: str, request: Request, db: Session = Depends(get_db)):
    config = _public_widget_config_payload(db, deployment_id)
    if not config:
        raise HTTPException(status_code=404, detail="Widget is not available")

    host = _origin_host(request)
    if not _host_allowed(host, config.get("allowed_domains") or []):
        raise HTTPException(status_code=403, detail="This domain is not allowed to use this widget")

    etag = str(config.get("etag") or "")
    if request.headers.get("if-none-match") == etag:
        headers = _origin_headers(request)
        headers["ETag"] = etag
        headers["Cache-Control"] = "public, max-age=60"
        return Response(status_code=304, headers=headers)

    headers = _origin_headers(request)
    headers["ETag"] = etag
    headers["Cache-Control"] = "public, max-age=60" # Cache for 60s
    
    return JSONResponse(
        headers=headers,
        content={
            "deployment_id": config["deployment_id"],
            "display_name": config["display_name"],
            "logo_url": config["logo_url"],
            "initial_messages": config["initial_messages"],
            "theme": config["theme"],
            "primary_color": config["primary_color"],
        },
    )


@public_router.post("/{deployment_id}/telemetry")
async def public_widget_telemetry(
    deployment_id: str,
    request: Request,
):
    """Log widget telemetry events for monitoring and analytics"""
    try:
        # Parse JSON manually to handle both dict and raw body
        body = await request.json()
        event = body.get("event", "unknown")
        data = body.get("data", {})
        
        logger.info(
            "widget_telemetry deployment_id=%s event=%s data=%s",
            deployment_id,
            event,
            data,
        )
        return {"status": "ok"}
    except Exception as e:
        logger.warning("widget_telemetry_failed deployment_id=%s error=%s", deployment_id, str(e))
        return {"status": "ok"}  # Still return ok to not break widget


@public_router.post("/{deployment_id}/chat")
async def public_widget_chat(
    deployment_id: str,
    payload: PublicChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    started = time.perf_counter()
    deployment = (
        db.query(models.WidgetDeployment)
        .options(joinedload(models.WidgetDeployment.agent))
        .filter(models.WidgetDeployment.deployment_id == deployment_id)
        .first()
    )
    if not deployment or not deployment.is_enabled:
        raise HTTPException(status_code=404, detail="Widget is not available")
    host = _origin_host(request)
    if not _host_allowed(host, deployment.allowed_domains or []):
        raise HTTPException(status_code=403, detail="This domain is not allowed to use this widget")

    visitor_id = payload.visitor_id or "anonymous"
    
    # Check for abuse signatures
    user_agent = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else "unknown"
    is_abuse, abuse_reason = detect_abuse_signature(
        deployment.deployment_id, visitor_id, ip, user_agent, payload.message
    )
    if is_abuse:
        logger.warning(
            "widget_abuse_detected deployment_id=%s ip=%s reason=%s",
            deployment.deployment_id, ip, abuse_reason
        )
        raise HTTPException(status_code=400, detail="Invalid request")
    
    await _check_rate_limit(deployment.deployment_id, visitor_id, request)

    agent = deployment.agent
    if not agent or not agent.instructions:
        raise HTTPException(status_code=404, detail="Widget is not available")

    session = None
    if payload.session_id:
        try:
            session_uuid = uuid.UUID(payload.session_id)
            session = (
                db.query(models.ChatSession)
                .filter(models.ChatSession.id == session_uuid, models.ChatSession.deployment_id == deployment.id)
                .first()
            )
        except ValueError:
            session = None
    
    # If identity provided, try to find or merge with existing session
    if payload.identity and payload.identity.get("externalId"):
        external_id = payload.identity.get("externalId")
        existing_session = (
            db.query(models.ChatSession)
            .filter(
                models.ChatSession.deployment_id == deployment.id,
                models.ChatSession.external_id == external_id
            )
            .order_by(models.ChatSession.last_active_at.desc())
            .first()
        )
        if existing_session:
            session = existing_session
    
    if not session:
        session = models.ChatSession(
            deployment_id=deployment.id,
            agent_id=agent.id,
            visitor_hash=_visitor_hash(deployment.id, visitor_id, request),
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # Update identity if provided
    if payload.identity:
        if payload.identity.get("externalId"):
            session.external_id = payload.identity.get("externalId")
        if payload.identity.get("email"):
            session.email = payload.identity.get("email")
        if payload.identity.get("name"):
            session.name = payload.identity.get("name")
        if payload.identity.get("metadata"):
            session.custom_metadata = {**(session.custom_metadata or {}), **payload.identity.get("metadata", {})}
        db.commit()

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    use_retrieval = bool(cfg.retrieval_enabled) if cfg else False
    top_k = min(int(cfg.retrieval_top_k) if cfg else 4, CHAT_RETRIEVAL_TOP_K_CAP)
    namespace = cfg.vector_store_namespace if cfg else None
    context = ""
    retrieval_ms = 0.0
    if use_retrieval and namespace:
        retrieval_started = time.perf_counter()
        try:
            context = await aretrieve_context(db, namespace, str(agent.id), payload.message, top_k=top_k)
        except Exception:
            logger.exception("public_widget_retrieval_failed deployment_id=%s agent_id=%s", deployment_id, agent.id)
        finally:
            retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

    history = _history_for_prompt(db, session.id)
    messages = build_messages(agent.instructions or "", context, payload.message, history=history)
    session_id_value = session.id
    agent_id_value = agent.id
    user_id_value = agent.user_id
    agent_model = agent.model
    user_message = payload.message

    db.add(models.ChatMessage(session_id=session_id_value, role="user", content=user_message, created_at=datetime.now(timezone.utc)))
    session.last_active_at = datetime.now(timezone.utc)
    db.commit()

    async def generate():
        answer_parts: list[str] = []
        stream_started = time.perf_counter()
        first_token_ms = None
        yield _sse("meta", {"session_id": str(session_id_value)})
        try:
            async for token in astream_answer(agent_model, messages):
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - stream_started) * 1000
                answer_parts.append(token)
                yield _sse("token", {"content": token})
            answer = "".join(answer_parts).strip()
            
            background_tasks.add_task(
                _log_public_chat,
                session_id=session_id_value,
                user_id=user_id_value,
                agent_id=agent_id_value,
                user_message=user_message,
                answer=answer
            )
            
            logger.info(
                "widget_chat_latency deployment_id=%s agent_id=%s retrieval_ms=%.2f llm_ttft_ms=%.2f total_ms=%.2f",
                deployment_id,
                agent_id_value,
                retrieval_ms,
                first_token_ms or 0.0,
                (time.perf_counter() - started) * 1000,
            )
            yield _sse("done", {"session_id": str(session_id_value)})
        except Exception:
            logger.exception("public_widget_generation_failed deployment_id=%s session_id=%s", deployment_id, session_id_value)
            yield _sse("error", {"detail": "Sorry, I could not answer that right now."})

    headers = _origin_headers(request)
    headers["Cache-Control"] = "no-cache"
    headers["X-Accel-Buffering"] = "no"
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers, background=background_tasks)


def _log_public_chat(session_id, user_id, agent_id, user_message, answer):
    db = BackgroundSession()
    try:
        db.add(models.ChatMessage(session_id=session_id, role="assistant", content=answer, created_at=datetime.now(timezone.utc)))
        db.add(models.UsageLog(
            user_id=user_id,
            agent_id=agent_id,
            message_content=user_message,
            response_content=answer,
            credits_used=1,
            timestamp=datetime.now(timezone.utc),
        ))
        session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
        if session:
            session.last_active_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("public_chat_log_failed session_id=%s agent_id=%s", session_id, agent_id)
    finally:
        db.close()
