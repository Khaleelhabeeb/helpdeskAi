import asyncio
import contextlib
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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Response, WebSocket, WebSocketDisconnect
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
from services.rag_service import build_messages, aretrieve_context, astream_answer, astream_answer_with_tools
from services.handoff_service import (
    TRANSFER_TO_HUMAN_TOOL,
    build_handoff_ack_message,
    broadcast_to_conversation,
    broadcast_to_humans_for_agent,
    get_or_create_conversation,
    transition_status,
)
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
    visitor_email: Optional[str] = Field(None, max_length=255, description="Visitor email (optional, for handoff)")
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
            # Bound Redis ops to 1.5s so a hanging Upstash connection doesn't
            # block the chat request. On timeout we fall back to in-memory limiter.
            count = await asyncio.wait_for(redis_client.incr(redis_key), timeout=1.5)
            if count == 1:
                try:
                    await asyncio.wait_for(redis_client.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS), timeout=1.0)
                except asyncio.TimeoutError:
                    logger.warning("redis_rate_limit_expire_timeout deployment_id=%s", deployment_public_id)
            if count > RATE_LIMIT_MAX_REQUESTS:
                logger.warning("rate_limit_exceeded deployment_id=%s ip=%s", deployment_public_id, ip)
                raise HTTPException(status_code=429, detail="Too many messages. Please wait a moment.")
            return
        except HTTPException:
            raise
        except asyncio.TimeoutError:
            logger.warning("redis_rate_limit_timeout deployment_id=%s", deployment_public_id)
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
        f'<script src="{base_url}/static/widget.js?v=2.1.2" '
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


async def _history_for_prompt_async(session_id: uuid.UUID, max_messages: int = 8, max_chars: int = 3000) -> list[dict[str, str]]:
    def _load_history() -> list[dict[str, str]]:
        history_db = BackgroundSession()
        try:
            return _history_for_prompt(history_db, session_id, max_messages=max_messages, max_chars=max_chars)
        finally:
            history_db.close()

    return await asyncio.to_thread(_load_history)


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
        .options(joinedload(models.WidgetDeployment.agent).joinedload(models.Agent.config))
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

    # ── Capture immutable agent/config scalars BEFORE any db.commit() expires them.
    # This prevents DetachedInstanceError inside the streaming generator (agent
    # becomes expired after db.commit() due to expire_on_commit=True).
    agent_instructions = agent.instructions or ""
    agent_name = agent.name or "Support"
    agent_model = agent.model
    agent_id_value = agent.id
    user_id_value = agent.user_id
    deployment_int_id = deployment.id
    deployment_public_id = deployment.deployment_id
    cfg = agent.config
    use_retrieval = bool(cfg.retrieval_enabled) if cfg else False
    top_k = min(int(cfg.retrieval_top_k) if cfg else 4, CHAT_RETRIEVAL_TOP_K_CAP)
    namespace = cfg.vector_store_namespace if cfg else None

    # Normalize visitor_email from explicit field or identity dict
    payload_visitor_email = (payload.visitor_email.strip() if payload.visitor_email else None) or None
    identity_email = None
    if payload.identity and payload.identity.get("email"):
        _raw = str(payload.identity.get("email")).strip()
        identity_email = _raw or None

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
            agent_id=agent_id_value,
            visitor_hash=_visitor_hash(deployment.id, visitor_id, request),
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
        )
        # persist explicit visitor_email on creation if provided
        if payload_visitor_email:
            session.email = payload_visitor_email
        elif identity_email:
            session.email = identity_email
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # Update identity if provided (and also sync visitor_email)
    _needs_commit = False
    if payload.identity:
        if payload.identity.get("externalId"):
            session.external_id = payload.identity.get("externalId")
            _needs_commit = True
        if identity_email and session.email != identity_email:
            session.email = identity_email
            _needs_commit = True
        if payload.identity.get("name"):
            session.name = payload.identity.get("name")
            _needs_commit = True
        if payload.identity.get("metadata"):
            session.custom_metadata = {**(session.custom_metadata or {}), **payload.identity.get("metadata", {})}
            _needs_commit = True
    # Also handle explicit visitor_email field
    if payload_visitor_email and not session.email:
        session.email = payload_visitor_email
        _needs_commit = True
    if _needs_commit:
        db.commit()
        try:
            db.refresh(session)
        except Exception:
            pass

    session_id_value = session.id
    session_email = session.email  # captured scalar for use inside generator
    user_message = payload.message

    # Resolve visitor_email for handoff (explicit field > identity > session)
    resolved_visitor_email = payload_visitor_email or identity_email or session_email

    # Get or create the Conversation row (handoff state machine)
    conversation = get_or_create_conversation(
        db,
        agent_id=agent_id_value,
        deployment_id=deployment_int_id,
        session_id=session_id_value,
        visitor_id=visitor_id,
    )
    conversation_id_value = conversation.id
    conv_status_value = conversation.status

    # ── Handoff states: do NOT call the LLM again ──────────────────────────
    # collecting_email / queued / resolved → bot is paused. A race (user
    # typing before the handoff SSE arrives) can still hit this endpoint.
    # Return a tiny SSE that re-asserts the current status so the widget
    # stays in the correct UI state and we avoid the "I'm connecting..." loop.
    if conv_status_value in ("collecting_email", "queued", "resolved"):
        background_tasks.add_task(
            _log_public_chat,
            session_id=session_id_value,
            user_id=user_id_value,
            agent_id=agent_id_value,
            user_message=user_message,
            answer="",
            sender_type="visitor",
        )

        async def _blocked_generate():
            yield _sse("meta", {
                "session_id": str(session_id_value),
                "conversation_id": str(conversation_id_value),
            })
            yield _sse("handoff", {
                "status": conv_status_value,
                "conversation_id": str(conversation_id_value),
            })
            if conv_status_value == "collecting_email":
                yield _sse("token", {"content": "Please share your email above so I can connect you with a teammate — I'll be right here once you do."})
            yield _sse("done", {
                "session_id": str(session_id_value),
                "conversation_id": str(conversation_id_value),
            })

        headers = _origin_headers(request)
        headers["Cache-Control"] = "no-cache"
        headers["X-Accel-Buffering"] = "no"
        return StreamingResponse(_blocked_generate(), media_type="text/event-stream", headers=headers, background=background_tasks)

    # ── Human state: visitor ↔ human chat (bot is out of the loop) ──────────
    # The widget is now directly talking to a human agent via WebSockets.
    # Persist the visitor message and broadcast it live so the human dashboard
    # sees it instantly. No LLM call.
    if conv_status_value == "human":
        # Persist visitor message synchronously so the human sees it immediately
        try:
            db.add(models.ChatMessage(
                session_id=session_id_value,
                role="user",
                content=user_message,
                sender_type="visitor",
                created_at=datetime.now(timezone.utc),
            ))
            # Bump conversation timestamp for correct ordering in dashboard
            conv = db.query(models.Conversation).filter(models.Conversation.id == conversation_id_value).first()
            if conv:
                conv.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            logger.exception("human_visitor_msg_save_failed conversation_id=%s", conversation_id_value)
            try:
                db.rollback()
            except Exception:
                pass

        # Broadcast to visitor's own WS (echo) and to all assigned human dashboards
        try:
            payload = {
                "type": "message",
                "sender_type": "visitor",
                "content": user_message,
                "conversation_id": str(conversation_id_value),
                "agent_id": str(agent_id_value),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            # Fire-and-forget in-process broadcast (also pg_notify for multi-instance)
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(lambda: _asyncio.ensure_future(broadcast_to_conversation(str(conversation_id_value), payload)))
                    loop.call_soon_threadsafe(lambda: _asyncio.ensure_future(broadcast_to_humans_for_agent(agent_id_value, payload)))
            except RuntimeError:
                pass
            # Best-effort pg_notify for other instances
            try:
                from services.handoff_service import pg_notify as _pg_notify
                _pg_notify(str(conversation_id_value), payload)
            except Exception:
                pass
        except Exception:
            logger.exception("human_visitor_broadcast_failed conversation_id=%s", conversation_id_value)

        async def _human_generate():
            yield _sse("meta", {
                "session_id": str(session_id_value),
                "conversation_id": str(conversation_id_value),
            })
            # No bot token — human will reply via WS
            yield _sse("done", {
                "session_id": str(session_id_value),
                "conversation_id": str(conversation_id_value),
            })

        headers = _origin_headers(request)
        headers["Cache-Control"] = "no-cache"
        headers["X-Accel-Buffering"] = "no"
        return StreamingResponse(_human_generate(), media_type="text/event-stream", headers=headers)

    async def generate():
        answer_parts: list[str] = []
        stream_started = time.perf_counter()
        first_token_ms = None
        retrieval_ms = 0.0
        chat_logged = False
        handoff_triggered = False

        yield _sse("meta", {
            "session_id": str(session_id_value),
            "conversation_id": str(conversation_id_value),
        })

        history_task = asyncio.create_task(_history_for_prompt_async(session_id_value))
        try:
            context = ""
            if use_retrieval and namespace:
                retrieval_started = time.perf_counter()
                try:
                    # Pass None for db inside async generator to avoid using expired request Session.
                    # aretrieve_context currently does not query DB tables (Milvus only), so None is safe.
                    # Keep fallback to catch any exception and continue with empty context.
                    context = await aretrieve_context(db, namespace, str(agent_id_value), user_message, top_k=top_k)
                except Exception:
                    logger.exception("public_widget_retrieval_failed deployment_id=%s agent_id=%s", deployment_id, agent_id_value)
                finally:
                    retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

            history = await history_task
            messages = build_messages(agent_instructions, context, user_message, history=history)

            async for event in astream_answer_with_tools(agent_model, messages, [TRANSFER_TO_HUMAN_TOOL]):
                if event["type"] == "token":
                    token = event["content"]
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - stream_started) * 1000
                    answer_parts.append(token)
                    yield _sse("token", {"content": token})

                elif event["type"] == "tool_call" and event["name"] == "transfer_to_human":
                    handoff_triggered = True
                    reason = event["arguments"].get("reason", "")
                    logger.info(
                        "handoff_triggered deployment_id=%s session_id=%s reason=%s",
                        deployment_id, session_id_value, reason,
                    )

                    # Determine next status: need email? → collecting_email, else → queued
                    # Use captured scalars to avoid DetachedInstanceError / AttributeError.
                    visitor_email_known = bool(resolved_visitor_email)
                    next_status = "queued" if visitor_email_known else "collecting_email"

                    # Persist the state transition — trigger email fallback check if queued.
                    # Use a fresh BackgroundSession in a thread to avoid thread-unsafe reuse of
                    # the request-scoped db Session (SQLAlchemy Session is not thread-safe).
                    def _do_handoff_transition():
                        bg_db = BackgroundSession()
                        try:
                            conv = bg_db.query(models.Conversation).filter(models.Conversation.id == conversation_id_value).first()
                            if not conv:
                                logger.warning("handoff_conversation_missing id=%s", conversation_id_value)
                                return
                            transition_status(
                                bg_db,
                                conv,
                                next_status,
                                visitor_email=resolved_visitor_email,
                                notify=True,
                                check_email_fallback=(next_status == "queued"),
                            )
                        except Exception:
                            logger.exception("handoff_transition_failed conversation_id=%s", conversation_id_value)
                        finally:
                            bg_db.close()

                    await asyncio.to_thread(_do_handoff_transition)

                    # Also fan-out in the main event loop (transition_status's thread-unsafe
                    # loop detection may miss in-process WS broadcast when called via to_thread).
                    try:
                        await broadcast_to_conversation(str(conversation_id_value), {
                            "type": "status_change",
                            "status": next_status,
                            "conversation_id": str(conversation_id_value),
                        })
                    except Exception:
                        logger.exception("handoff_broadcast_failed conversation_id=%s", conversation_id_value)
                    try:
                        await broadcast_to_humans_for_agent(agent_id_value, {
                            "type": "status_change",
                            "status": next_status,
                            "conversation_id": str(conversation_id_value),
                            "agent_id": str(agent_id_value),
                        })
                    except Exception:
                        logger.exception("handoff_human_broadcast_failed agent_id=%s", agent_id_value)

                    # Send the bot's acknowledgement message
                    ack = build_handoff_ack_message(agent_name)
                    answer_parts.append(ack)
                    yield _sse("token", {"content": ack})

                    # Tell the widget about the status change
                    yield _sse("handoff", {
                        "status": next_status,
                        "conversation_id": str(conversation_id_value),
                    })
                    break  # Stop streaming after handoff

            answer = "".join(answer_parts).strip()

            background_tasks.add_task(
                _log_public_chat,
                session_id=session_id_value,
                user_id=user_id_value,
                agent_id=agent_id_value,
                user_message=user_message,
                answer=answer,
                sender_type="bot",
            )
            chat_logged = True

            logger.info(
                "widget_chat_latency deployment_id=%s agent_id=%s retrieval_ms=%.2f llm_ttft_ms=%.2f total_ms=%.2f handoff=%s",
                deployment_id,
                agent_id_value,
                retrieval_ms,
                first_token_ms or 0.0,
                (time.perf_counter() - started) * 1000,
                handoff_triggered,
            )
            yield _sse("done", {
                "session_id": str(session_id_value),
                "conversation_id": str(conversation_id_value),
            })
        except asyncio.CancelledError:
            logger.info("public_widget_stream_cancelled deployment_id=%s session_id=%s", deployment_id, session_id_value)
            if not history_task.done():
                history_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await history_task
            if not chat_logged:
                with contextlib.suppress(Exception):
                    await asyncio.shield(
                        asyncio.to_thread(
                            _log_public_chat,
                            session_id_value,
                            user_id_value,
                            agent_id_value,
                            user_message,
                            "",
                            "bot",
                        )
                    )
            raise
        except Exception:
            logger.exception("public_widget_generation_failed deployment_id=%s session_id=%s", deployment_id, session_id_value)
            if not history_task.done():
                history_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await history_task
            background_tasks.add_task(
                _log_public_chat,
                session_id=session_id_value,
                user_id=user_id_value,
                agent_id=agent_id_value,
                user_message=user_message,
                answer="",
                sender_type="bot",
            )
            chat_logged = True
            yield _sse("error", {"detail": "Sorry, I could not answer that right now."})

    headers = _origin_headers(request)
    headers["Cache-Control"] = "no-cache"
    headers["X-Accel-Buffering"] = "no"
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers, background=background_tasks)


# ── Email capture endpoint ─────────────────────────────────────────────────────

class EmailCaptureRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


@public_router.post("/{deployment_id}/conversations/{conversation_id}/email")
async def capture_visitor_email(
    deployment_id: str,
    conversation_id: str,
    payload: EmailCaptureRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Called by the widget after the visitor submits their email in the
    collecting_email inline card.  Transitions the conversation to 'queued'
    and broadcasts the status change via pg_notify + in-process WS registry.
    """
    # Validate deployment
    deployment = (
        db.query(models.WidgetDeployment)
        .filter(models.WidgetDeployment.deployment_id == deployment_id)
        .first()
    )
    if not deployment or not deployment.is_enabled:
        raise HTTPException(status_code=404, detail="Widget is not available")

    host = _origin_host(request)
    if not _host_allowed(host, deployment.allowed_domains or []):
        raise HTTPException(status_code=403, detail="Domain not allowed")

    # Basic email format check
    import re as _re
    if not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", payload.email):
        raise HTTPException(status_code=422, detail="Invalid email address")

    # Load conversation
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conv_uuid,
            models.Conversation.deployment_id == deployment.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.status not in ("bot", "collecting_email"):
        # Already transitioned — idempotent OK
        return {"status": conv.status, "conversation_id": str(conv.id)}

    transition_status(
        db,
        conv,
        "queued",
        visitor_email=payload.email,
        notify=True,
        check_email_fallback=True,
    )

    # Fan-out to any open WebSocket for this conversation
    await broadcast_to_conversation(str(conv.id), {
        "type": "status_change",
        "status": "queued",
        "conversation_id": str(conv.id),
    })

    logger.info(
        "visitor_email_captured deployment_id=%s conversation_id=%s",
        deployment_id, conv.id,
    )
    return {"status": "queued", "conversation_id": str(conv.id)}


# ── Widget WebSocket endpoint ──────────────────────────────────────────────────

@public_router.websocket("/ws/{conversation_id}")
async def widget_ws(
    websocket: WebSocket,
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """
    Real-time channel for a visitor's conversation.

    The widget connects here after a handoff is triggered.  The server pushes
    JSON frames whenever the conversation status changes or a human agent sends
    a message.

    Frame shapes (server → client):
        {"type": "status_change", "status": "...", "conversation_id": "..."}
        {"type": "message", "sender_type": "human_agent", "content": "...", "sender_name": "..."}
        {"type": "agent_claimed", "agent_name": "..."}
        {"type": "resolved"}
        {"type": "ping"}   ← heartbeat every 25 s

    Frame shapes (client → server):
        {"type": "pong"}   ← heartbeat reply (optional)
    """
    # Validate conversation exists
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        await websocket.close(code=4004)
        return

    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_uuid).first()
    if not conv:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    from services.handoff_service import register_ws, unregister_ws

    q = await register_ws(conversation_id)
    logger.info("widget_ws_connected conversation_id=%s", conversation_id)

    # Send current status immediately so the widget can sync on reconnect
    await websocket.send_json({
        "type": "status_change",
        "status": conv.status,
        "conversation_id": conversation_id,
        **({"agent_name": conv.assigned_human_agent.name or conv.assigned_human_agent.email}
           if conv.assigned_human_agent else {}),
    })

    ping_interval = 25  # seconds

    async def _pump():
        """Drain the queue and forward to the WebSocket."""
        while True:
            msg = await q.get()
            try:
                await websocket.send_json(msg)
            except Exception:
                break

    pump_task = asyncio.create_task(_pump())

    try:
        while True:
            # Wait for a client frame or timeout (heartbeat)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=ping_interval)
                # Client frames are informational only (pong, etc.)
            except asyncio.TimeoutError:
                # Send ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        await unregister_ws(conversation_id, q)
        logger.info("widget_ws_disconnected conversation_id=%s", conversation_id)


# ── Widget conversation history (spec §7, API §6) ───────────────────────────────

class WidgetConversationCreate(BaseModel):
    visitor_id: str = Field(..., min_length=1, max_length=120)
    visitor_email: Optional[str] = Field(None, max_length=255)


@public_router.get("/{deployment_id}/conversations")
def list_widget_conversations(
    deployment_id: str,
    visitor_id: str = Query(..., min_length=1, max_length=120),
    request: Request = None,  # type: ignore
    db: Session = Depends(get_db),
):
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.deployment_id == deployment_id).first()
    if not deployment or not deployment.is_enabled:
        raise HTTPException(status_code=404, detail="Widget is not available")
    if request is not None:
        host = _origin_host(request)
        if host and not _host_allowed(host, deployment.allowed_domains or []):
            raise HTTPException(status_code=403, detail="Domain not allowed")
    rows = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.deployment_id == deployment.id,
            models.Conversation.visitor_id == visitor_id,
        )
        .order_by(models.Conversation.updated_at.desc())
        .limit(50)
        .all()
    )
    out = []
    for c in rows:
        # last message preview
        preview = None
        if c.session_id:
            last = (
                db.query(models.ChatMessage)
                .filter(models.ChatMessage.session_id == c.session_id)
                .order_by(models.ChatMessage.created_at.desc())
                .first()
            )
            if last:
                preview = last.content[:120]
        out.append({
            "id": str(c.id),
            "status": c.status,
            "visitor_email": c.visitor_email,
            "assigned_human_agent_id": str(c.assigned_human_agent_id) if c.assigned_human_agent_id else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "preview": preview,
        })
    return {"conversations": out}


@public_router.post("/{deployment_id}/conversations")
def create_widget_conversation(
    deployment_id: str,
    payload: WidgetConversationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.deployment_id == deployment_id).first()
    if not deployment or not deployment.is_enabled:
        raise HTTPException(status_code=404, detail="Widget is not available")
    host = _origin_host(request)
    if host and not _host_allowed(host, deployment.allowed_domains or []):
        raise HTTPException(status_code=403, detail="Domain not allowed")
    # Create a new ChatSession + Conversation row (visitor can have multiple)
    visitor_hash = _visitor_hash(deployment.id, payload.visitor_id, request)
    session = models.ChatSession(
        deployment_id=deployment.id,
        agent_id=deployment.agent_id,
        visitor_hash=visitor_hash,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    # propagate email if given
    if payload.visitor_email:
        session.email = payload.visitor_email
    db.add(session)
    db.flush()  # get session.id
    conv = models.Conversation(
        agent_id=deployment.agent_id,
        deployment_id=deployment.id,
        session_id=session.id,
        visitor_id=payload.visitor_id,
        visitor_email=payload.visitor_email,
        status="bot",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "id": str(conv.id),
        "session_id": str(session.id),
        "status": conv.status,
        "visitor_id": conv.visitor_id,
    }


@public_router.get("/{deployment_id}/conversations/{conversation_id}/messages")
def get_conversation_messages(
    deployment_id: str,
    conversation_id: str,
    visitor_id: str = Query(..., min_length=1, max_length=120),
    db: Session = Depends(get_db),
):
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.deployment_id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Widget not found")
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == cid,
        models.Conversation.deployment_id == deployment.id,
        models.Conversation.visitor_id == visitor_id,
    ).first()
    if not conv or not conv.session_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == conv.session_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    return {
        "conversation_id": str(conv.id),
        "status": conv.status,
        "assigned_human_agent_id": str(conv.assigned_human_agent_id) if conv.assigned_human_agent_id else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sender_type": m.sender_type,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


def _log_public_chat(session_id, user_id, agent_id, user_message, answer, sender_type="bot"):
    db = BackgroundSession()
    try:
        db.add(models.ChatMessage(
            session_id=session_id,
            role="user",
            content=user_message,
            sender_type="visitor",
            created_at=datetime.now(timezone.utc),
        ))
        if answer:
            db.add(models.ChatMessage(
                session_id=session_id,
                role="assistant",
                content=answer,
                sender_type=sender_type,
                created_at=datetime.now(timezone.utc),
            ))
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
