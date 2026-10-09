import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from services.actions import (
    MAX_ACTIONS_PER_AGENT,
    ActionValidationError,
    encrypt_headers,
    execute_action,
    masked_headers,
    to_runtime,
    validate_action_name,
    validate_headers,
    validate_parameters,
    validate_url_template,
)
from utils.jwt import get_current_user
from utils.rate_limit import create_limiter

router = APIRouter()
limiter = create_limiter()


class ActionParameter(BaseModel):
    name: str = Field(..., max_length=40)
    type: Literal["string", "number", "boolean"] = "string"
    description: str = Field("", max_length=300)
    required: bool = True


class ActionHeader(BaseModel):
    name: str = Field(..., max_length=64)
    value: str = Field("", max_length=2000)


class ActionIn(BaseModel):
    name: str = Field(..., max_length=48)
    description: str = Field(..., min_length=10, max_length=1000)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    url: str = Field(..., max_length=2000)
    parameters: list[ActionParameter] = Field(default_factory=list)
    headers: list[ActionHeader] = Field(default_factory=list)
    enabled: bool = True
    timeout_seconds: int = Field(10, ge=1, le=30)


class ActionPatch(BaseModel):
    enabled: Optional[bool] = None


class ActionTestIn(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


def _owned_agent(db: Session, agent_id: uuid.UUID, user) -> models.Agent:
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _owned_action(db: Session, agent_id: uuid.UUID, action_id: uuid.UUID) -> models.AgentAction:
    action = (
        db.query(models.AgentAction)
        .filter(models.AgentAction.id == action_id, models.AgentAction.agent_id == agent_id)
        .first()
    )
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


def _out(action: models.AgentAction) -> dict:
    return {
        "id": str(action.id),
        "name": action.name,
        "description": action.description,
        "method": action.method,
        "url": action.url,
        "parameters": action.parameters or [],
        # Secrets never leave the server; the UI sends the mask back to keep a value
        "headers": masked_headers(action.headers_encrypted),
        "enabled": action.enabled,
        "timeout_seconds": action.timeout_seconds,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
    }


def _apply(action: models.AgentAction, payload: ActionIn, db: Session, agent_id: uuid.UUID) -> None:
    try:
        name = validate_action_name(payload.name)
        params = validate_parameters([p.model_dump() for p in payload.parameters])
        url = validate_url_template(payload.url, params)
        headers = validate_headers([h.model_dump() for h in payload.headers], action.headers_encrypted)
    except ActionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    clash_q = db.query(models.AgentAction.id).filter(
        models.AgentAction.agent_id == agent_id, models.AgentAction.name == name
    )
    if action.id is not None:
        clash_q = clash_q.filter(models.AgentAction.id != action.id)
    clash = clash_q.first()
    if clash:
        raise HTTPException(status_code=409, detail="This agent already has an action with that name")

    action.name = name
    action.description = payload.description.strip()
    action.method = payload.method
    action.url = url
    action.parameters = params
    action.headers_encrypted = encrypt_headers(headers)
    action.enabled = payload.enabled
    action.timeout_seconds = payload.timeout_seconds
    action.updated_at = datetime.now(timezone.utc)


@router.get("/{agent_id}/actions")
def list_actions(agent_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _owned_agent(db, agent_id, user)
    rows = (
        db.query(models.AgentAction)
        .filter(models.AgentAction.agent_id == agent_id)
        .order_by(models.AgentAction.created_at)
        .all()
    )
    return [_out(r) for r in rows]


@router.post("/{agent_id}/actions", status_code=201)
def create_action(agent_id: uuid.UUID, payload: ActionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _owned_agent(db, agent_id, user)
    count = db.query(models.AgentAction).filter(models.AgentAction.agent_id == agent_id).count()
    if count >= MAX_ACTIONS_PER_AGENT:
        raise HTTPException(status_code=422, detail=f"An agent can have at most {MAX_ACTIONS_PER_AGENT} actions")
    action = models.AgentAction(agent_id=agent_id, created_at=datetime.now(timezone.utc))
    _apply(action, payload, db, agent_id)
    db.add(action)
    db.commit()
    db.refresh(action)
    return _out(action)


@router.put("/{agent_id}/actions/{action_id}")
def update_action(
    agent_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: ActionIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _owned_agent(db, agent_id, user)
    action = _owned_action(db, agent_id, action_id)
    _apply(action, payload, db, agent_id)
    db.commit()
    db.refresh(action)
    return _out(action)


@router.patch("/{agent_id}/actions/{action_id}")
def toggle_action(
    agent_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: ActionPatch,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _owned_agent(db, agent_id, user)
    action = _owned_action(db, agent_id, action_id)
    if payload.enabled is not None:
        action.enabled = payload.enabled
        action.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(action)
    return _out(action)


@router.delete("/{agent_id}/actions/{action_id}", status_code=204)
def delete_action(agent_id: uuid.UUID, action_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _owned_agent(db, agent_id, user)
    action = _owned_action(db, agent_id, action_id)
    db.delete(action)
    db.commit()


@router.post("/{agent_id}/actions/{action_id}/test")
@limiter.limit("20/minute")
async def test_action(
    request: Request,
    agent_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: ActionTestIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Run the saved action once with sample arguments so owners can check it before going live."""
    _owned_agent(db, agent_id, user)
    runtime = to_runtime(_owned_action(db, agent_id, action_id))
    result = await execute_action(runtime, payload.arguments)
    return {
        "ok": result.ok,
        "status": result.status,
        "error": result.error,
        "duration_ms": round(result.duration_ms),
        "body": result.body[:8000],
    }
