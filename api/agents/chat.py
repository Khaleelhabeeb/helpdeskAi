import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from db.database import SessionLocal
from services.rag_service import build_messages, aretrieve_context, astream_answer
from utils.jwt import get_current_user
from utils.rate_limit import create_limiter

router = APIRouter()
logger = logging.getLogger(__name__)
limiter = create_limiter()


class ChatRequest(BaseModel):
    message: str
    unique_id: Optional[str] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{agent_id}")
@limiter.limit("30/minute")
async def chat_with_agent(
    request: Request,
    agent_id: str,
    chat: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = db.query(models.Agent).filter(
        models.Agent.id == agent_id,
        models.Agent.user_id == user.id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or access denied")
    if not agent.instructions:
        raise HTTPException(status_code=400, detail="Agent has no instructions set yet")

    cfg = db.query(models.AgentConfig).filter(models.AgentConfig.agent_id == agent.id).first()
    use_retrieval = bool(cfg.retrieval_enabled) if cfg else False
    top_k = int(cfg.retrieval_top_k) if cfg else 4
    namespace = cfg.vector_store_namespace if cfg else None
    context = ""
    if use_retrieval and namespace:
        try:
            context = await aretrieve_context(db, namespace, str(agent.id), chat.message, top_k=top_k)
        except Exception:
            logger.exception("chat_retrieval_failed agent_id=%s user_id=%s", agent.id, user.id)

    unique_id = chat.unique_id or str(uuid.uuid4())
    messages = build_messages(agent.instructions or "", context, chat.message)

    async def generate():
        answer_parts: list[str] = []
        yield _sse("meta", {"unique_id": unique_id})
        try:
            async for token in astream_answer(agent.model, messages):
                answer_parts.append(token)
                yield _sse("token", {"content": token})

            answer = "".join(answer_parts)
            background_tasks.add_task(
                _log_usage,
                user_id=user.id,
                agent_id=agent.id,
                message_content=chat.message,
                response_content=answer
            )
            yield _sse("done", {"unique_id": unique_id})
        except Exception as exc:
            logger.exception("chat_generation_failed agent_id=%s user_id=%s unique_id=%s", agent_id, user.id, unique_id)
            yield _sse("error", {"detail": "Sorry, I could not answer that right now."})

    return StreamingResponse(generate(), media_type="text/event-stream")


def _log_usage(user_id, agent_id, message_content, response_content):
    db = SessionLocal()
    try:
        db.add(models.UsageLog(
            user_id=user_id,
            agent_id=agent_id,
            message_content=message_content,
            response_content=response_content,
            credits_used=1,
            timestamp=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("usage_log_failed user_id=%s agent_id=%s", user_id, agent_id)
    finally:
        db.close()
