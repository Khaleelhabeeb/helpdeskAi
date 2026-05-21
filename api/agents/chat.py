import json
import logging
import os
import time
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
from services.chat_runtime import get_agent_runtime
from services.rag_service import build_messages, aretrieve_context, astream_answer
from utils.jwt import get_current_user
from utils.rate_limit import create_limiter

router = APIRouter()
logger = logging.getLogger(__name__)
limiter = create_limiter()
CHAT_RETRIEVAL_TOP_K_CAP = int(os.getenv("CHAT_RETRIEVAL_TOP_K_CAP", "3"))


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
    started = time.perf_counter()
    runtime = await get_agent_runtime(db, agent_id, user.id)
    lookup_ms = (time.perf_counter() - started) * 1000
    if not runtime:
        raise HTTPException(status_code=404, detail="Agent not found or access denied")
    if not runtime.instructions:
        raise HTTPException(status_code=400, detail="Agent has no instructions set yet")

    context = ""
    retrieval_ms = 0.0
    if runtime.retrieval_enabled and runtime.vector_store_namespace:
        retrieval_started = time.perf_counter()
        try:
            context = await aretrieve_context(
                db,
                runtime.vector_store_namespace,
                runtime.id,
                chat.message,
                top_k=min(runtime.retrieval_top_k, CHAT_RETRIEVAL_TOP_K_CAP),
            )
        except Exception:
            logger.exception("chat_retrieval_failed agent_id=%s user_id=%s", runtime.id, user.id)
        finally:
            retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

    unique_id = chat.unique_id or str(uuid.uuid4())
    messages = build_messages(runtime.instructions, context, chat.message)

    async def generate():
        answer_parts: list[str] = []
        stream_started = time.perf_counter()
        first_token_ms = None
        yield _sse("meta", {"unique_id": unique_id})
        try:
            async for token in astream_answer(runtime.model, messages):
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - stream_started) * 1000
                answer_parts.append(token)
                yield _sse("token", {"content": token})

            answer = "".join(answer_parts)
            background_tasks.add_task(
                _log_usage,
                user_id=user.id,
                agent_id=runtime.id,
                message_content=chat.message,
                response_content=answer
            )
            logger.info(
                "chat_latency agent_id=%s lookup_ms=%.2f retrieval_ms=%.2f llm_ttft_ms=%.2f total_ms=%.2f",
                runtime.id,
                lookup_ms,
                retrieval_ms,
                first_token_ms or 0.0,
                (time.perf_counter() - started) * 1000,
            )
            yield _sse("done", {"unique_id": unique_id})
        except Exception:
            logger.exception("chat_generation_failed agent_id=%s user_id=%s unique_id=%s", agent_id, user.id, unique_id)
            yield _sse("error", {"detail": "Sorry, I could not answer that right now."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=background_tasks,
    )


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
