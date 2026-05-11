import hashlib
import json
import time
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from db.database import SessionLocal
from models.widget_deployment import new_deployment_id
from services.rag_service import build_messages, retrieve_context, stream_answer
from utils.jwt import get_current_user

router = APIRouter()
public_router = APIRouter()

DEFAULT_INITIAL_MESSAGES = ["Hi! What can I help you with?"]
DEFAULT_ALLOWED_DOMAINS = ["localhost", "127.0.0.1"]
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30
_rate_buckets: dict[str, list[float]] = {}


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


MAX_RATE_BUCKETS = 10000

def _check_rate_limit(deployment_public_id: str, visitor_id: str, request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"{deployment_public_id}:{ip}:{visitor_id}"
    now = time.time()

    if len(_rate_buckets) > MAX_RATE_BUCKETS:
        for k in list(_rate_buckets.keys()):
            _rate_buckets[k] = [stamp for stamp in _rate_buckets[k] if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
            if not _rate_buckets[k]:
                del _rate_buckets[k]
        if len(_rate_buckets) > MAX_RATE_BUCKETS:
            _rate_buckets.clear()

    bucket = [stamp for stamp in _rate_buckets.get(key, []) if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
    if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many messages. Please wait a moment.")
    bucket.append(now)
    _rate_buckets[key] = bucket


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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
    deployment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deployment)
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
    deployment.deployment_id = new_deployment_id()
    deployment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deployment)
    return _deployment_out(deployment, request)


@public_router.get("/{deployment_id}/config")
def get_public_widget_config(deployment_id: str, request: Request, db: Session = Depends(get_db)):
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.deployment_id == deployment_id).first()
    if not deployment or not deployment.is_enabled:
        raise HTTPException(status_code=404, detail="Widget is not available")
    host = _origin_host(request)
    if not _host_allowed(host, deployment.allowed_domains or []):
        raise HTTPException(status_code=403, detail="This domain is not allowed to use this widget")
    return JSONResponse(
        headers=_origin_headers(request),
        content={
            "deployment_id": deployment.deployment_id,
            "display_name": deployment.display_name,
            "logo_url": deployment.logo_url or "",
            "initial_messages": deployment.initial_messages or DEFAULT_INITIAL_MESSAGES,
            "theme": deployment.theme,
            "primary_color": deployment.primary_color,
        },
    )


@public_router.post("/{deployment_id}/chat")
async def public_widget_chat(deployment_id: str, payload: PublicChatRequest, request: Request, db: Session = Depends(get_db)):
    deployment = db.query(models.WidgetDeployment).filter(models.WidgetDeployment.deployment_id == deployment_id).first()
    if not deployment or not deployment.is_enabled:
        raise HTTPException(status_code=404, detail="Widget is not available")
    host = _origin_host(request)
    if not _host_allowed(host, deployment.allowed_domains or []):
        raise HTTPException(status_code=403, detail="This domain is not allowed to use this widget")

    visitor_id = payload.visitor_id or "anonymous"
    _check_rate_limit(deployment.deployment_id, visitor_id, request)

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
    if not session:
        session = models.ChatSession(
            deployment_id=deployment.id,
            agent_id=agent.id,
            visitor_hash=_visitor_hash(deployment.id, visitor_id, request),
            created_at=datetime.utcnow(),
            last_active_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    use_retrieval = bool(cfg.retrieval_enabled) if cfg else False
    top_k = int(cfg.retrieval_top_k) if cfg else 4
    namespace = cfg.vector_store_namespace if cfg else None
    context = ""
    if use_retrieval and namespace:
        try:
            context = retrieve_context(db, namespace, str(agent.id), payload.message, top_k=top_k)
        except Exception as exc:
            print(f"[public widget chat] retrieval failed: {exc}")

    history = _history_for_prompt(db, session.id)
    messages = build_messages(agent.instructions or "", context, payload.message, history=history)
    session_id_value = session.id
    agent_id_value = agent.id
    user_id_value = agent.user_id
    agent_model = agent.model
    user_message = payload.message

    db.add(models.ChatMessage(session_id=session_id_value, role="user", content=user_message, created_at=datetime.utcnow()))
    session.last_active_at = datetime.utcnow()
    db.commit()

    def generate():
        answer_parts: list[str] = []
        yield _sse("meta", {"session_id": str(session_id_value)})
        try:
            for token in stream_answer(agent_model, messages):
                answer_parts.append(token)
                yield _sse("token", {"content": token})
            answer = "".join(answer_parts).strip()
            stream_db = SessionLocal()
            try:
                stream_db.add(models.ChatMessage(session_id=session_id_value, role="assistant", content=answer, created_at=datetime.utcnow()))
                stream_db.add(models.UsageLog(
                    user_id=user_id_value,
                    agent_id=agent_id_value,
                    message_content=user_message,
                    response_content=answer,
                    credits_used=1,
                    timestamp=datetime.utcnow(),
                ))
                stream_session = stream_db.query(models.ChatSession).filter(models.ChatSession.id == session_id_value).first()
                if stream_session:
                    stream_session.last_active_at = datetime.utcnow()
                stream_db.commit()
            finally:
                stream_db.close()
            yield _sse("done", {"session_id": str(session_id_value)})
        except Exception as exc:
            print(f"[public widget chat] generation failed: {exc}")
            yield _sse("error", {"detail": "Sorry, I could not answer that right now."})

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_origin_headers(request))
