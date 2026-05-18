import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from db.database import SessionLocal
from services import cache_keys
from services.rag_service import build_messages, aretrieve_context, astream_answer
from services.redis_client import acache_get_json, acache_set_json, cache_delete
from utils.jwt import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

AGENT_RUNTIME_CACHE_TTL_SECONDS = 30
CHAT_MESSAGE_MAX_LENGTH = 4000


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=CHAT_MESSAGE_MAX_LENGTH)
    unique_id: Optional[str] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _get_agent_runtime(db: Session, agent_id: str) -> Optional[dict]:
    cache_key = cache_keys.agent_runtime(agent_id)
    cached = await acache_get_json(cache_key)
    if cached:
        return cached

    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        return None
    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    runtime = {
        "agent_id": str(agent.id),
        "user_id": agent.user_id,
        "model": agent.model,
        "instructions": agent.instructions or "",
        "retrieval_enabled": bool(cfg.retrieval_enabled) if cfg else False,
        "retrieval_top_k": int(cfg.retrieval_top_k) if cfg else 4,
        "vector_store_namespace": cfg.vector_store_namespace if cfg else None,
    }
    await acache_set_json(cache_key, runtime, AGENT_RUNTIME_CACHE_TTL_SECONDS)
    return runtime


@router.post("/{agent_id}")
async def chat_with_agent(
    agent_id: str,
    chat: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    runtime = await _get_agent_runtime(db, agent_id)
    if not runtime or runtime["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Agent not found or access denied")
    if not runtime["instructions"]:
        raise HTTPException(status_code=400, detail="Agent has no instructions set yet")

    context = ""
    if runtime["retrieval_enabled"] and runtime["vector_store_namespace"]:
        try:
            context = await aretrieve_context(
                db,
                runtime["vector_store_namespace"],
                runtime["agent_id"],
                chat.message,
                top_k=runtime["retrieval_top_k"],
            )
        except Exception:
            logger.exception("chat_retrieval_failed agent_id=%s user_id=%s", agent_id, user.id)

    unique_id = chat.unique_id or str(uuid.uuid4())
    messages = build_messages(runtime["instructions"], context, chat.message)
    user_id_value = user.id
    agent_id_value = runtime["agent_id"]
    agent_model = runtime["model"]
    user_message = chat.message
    db.close()

    async def generate():
        answer_parts: list[str] = []
        yield _sse("meta", {"unique_id": unique_id})
        try:
            async for token in astream_answer(agent_model, messages):
                answer_parts.append(token)
                yield _sse("token", {"content": token})

            answer = "".join(answer_parts)
            background_tasks.add_task(
                _log_usage,
                user_id=user_id_value,
                agent_id=agent_id_value,
                message_content=user_message,
                response_content=answer,
            )
            yield _sse("done", {"unique_id": unique_id})
        except Exception:
            logger.exception(
                "chat_generation_failed agent_id=%s user_id=%s unique_id=%s",
                agent_id,
                user_id_value,
                unique_id,
            )
            yield _sse("error", {"detail": "Sorry, I could not answer that right now."})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _log_usage(user_id, agent_id, message_content: str, response_content: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            models.UsageLog(
                user_id=user_id,
                agent_id=agent_id,
                message_content=message_content,
                response_content=response_content,
                credits_used=1,
                timestamp=datetime.utcnow(),
            )
        )
        db.commit()
        cache_delete(cache_keys.dashboard_summary(user_id))
    except Exception:
        db.rollback()
        logger.exception("usage_log_failed user_id=%s agent_id=%s", user_id, agent_id)
    finally:
        db.close()
