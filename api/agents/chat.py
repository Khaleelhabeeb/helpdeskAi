import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from services.rag_service import build_messages, retrieve_context, stream_answer
from utils.jwt import get_current_user

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    unique_id: Optional[str] = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{agent_id}")
def chat_with_agent(
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
        context = retrieve_context(db, namespace, str(agent.id), chat.message, top_k=top_k)

    unique_id = chat.unique_id or str(uuid.uuid4())
    messages = build_messages(agent.instructions or "", context, chat.message)

    def generate():
        answer_parts: list[str] = []
        yield _sse("meta", {"unique_id": unique_id})
        try:
            for token in stream_answer(agent.model, messages):
                answer_parts.append(token)
                yield _sse("token", {"content": token})

            answer = "".join(answer_parts)
            db.add(models.UsageLog(
                user_id=user.id,
                agent_id=agent.id,
                message_content=chat.message,
                response_content=answer,
                credits_used=1,
                timestamp=datetime.utcnow(),
            ))
            db.commit()
            yield _sse("done", {"unique_id": unique_id})
        except Exception as exc:
            db.rollback()
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream")
