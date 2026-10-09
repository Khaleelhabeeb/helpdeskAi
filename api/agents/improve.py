"""Answer quality: unanswered-questions report and owner-written corrections (stored as Q&A knowledge)."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.auth.auth import get_db
from db import models
from services.answer_quality import (
    CORRECTED,
    DISMISSED,
    UNANSWERED,
    looks_unanswered,
    normalize_question,
)
from services.kb_limits import PayloadTooLargeError
from services.kb_text import KBQueueFullError, create_text_kb, delete_kb_completely
from services.image_upload import ImageUploadError
from utils.jwt import get_current_user

router = APIRouter()

SCAN_LIMIT = 3000  # newest bot replies considered per report
MAX_MESSAGE_IDS = 200


class CorrectionIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    answer: str = Field(..., min_length=1, max_length=8000)
    # Bot replies this fixes; they leave the unanswered report
    message_ids: list[int] = Field(default_factory=list, max_length=MAX_MESSAGE_IDS)


class DismissIn(BaseModel):
    message_ids: list[int] = Field(..., min_length=1, max_length=MAX_MESSAGE_IDS)


def _owned_agent(db: Session, agent_id: uuid.UUID, user) -> models.Agent:
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id, models.Agent.user_id == user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _bot_messages_for_agent(db: Session, agent_id: uuid.UUID):
    return (
        db.query(models.ChatMessage)
        .join(models.ChatSession, models.ChatSession.id == models.ChatMessage.session_id)
        .filter(models.ChatSession.agent_id == agent_id, models.ChatMessage.sender_type == "bot")
    )


def _mark_messages(db: Session, agent_id: uuid.UUID, message_ids: list[int], status: str) -> int:
    if not message_ids:
        return 0
    rows = _bot_messages_for_agent(db, agent_id).filter(models.ChatMessage.id.in_(message_ids)).all()
    for r in rows:
        r.answer_status = status
    return len(rows)


def _qa_text(question: str, answer: str) -> str:
    return f"Q: {question.strip()}\nA: {answer.strip()}\n"


def _correction_out(c: models.AnswerCorrection, kb_status: Optional[str]) -> dict:
    return {
        "id": str(c.id),
        "question": c.question,
        "answer": c.answer,
        "kb_id": str(c.kb_id) if c.kb_id else None,
        "kb_status": kb_status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


async def _store_qa(db: Session, agent: models.Agent, question: str, answer: str) -> models.KnowledgeBase:
    title = f"Q&A: {question.strip()[:80]}"
    try:
        return await create_text_kb(db, agent, title, _qa_text(question, answer))
    except PayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except ImageUploadError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except KBQueueFullError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{agent_id}/unanswered")
def unanswered_report(
    agent_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _owned_agent(db, agent_id, user)
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    window = _bot_messages_for_agent(db, agent_id).filter(models.ChatMessage.created_at >= since)
    total_replies = window.count()

    # Tagged rows, plus untagged history (pre-tagging) checked with the phrase heuristic
    candidates = (
        window.filter(or_(models.ChatMessage.answer_status == UNANSWERED, models.ChatMessage.answer_status.is_(None)))
        .order_by(models.ChatMessage.id.desc())
        .limit(SCAN_LIMIT)
        .all()
    )
    flagged = [m for m in candidates if m.answer_status == UNANSWERED or looks_unanswered(m.content)]

    # Pair each reply with the visitor message right before it in the same session
    questions: dict[int, models.ChatMessage] = {}
    session_ids = {m.session_id for m in flagged}
    if session_ids:
        visitor_rows = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.session_id.in_(session_ids),
                models.ChatMessage.sender_type == "visitor",
                models.ChatMessage.created_at >= since - timedelta(days=1),
            )
            .order_by(models.ChatMessage.id)
            .all()
        )
        by_session: dict = {}
        for v in visitor_rows:
            by_session.setdefault(v.session_id, []).append(v)
        for m in flagged:
            prior = [v for v in by_session.get(m.session_id, []) if v.id < m.id]
            if prior:
                questions[m.id] = prior[-1]

    corrected_keys = {
        k for (k,) in db.query(models.AnswerCorrection.question_key).filter(models.AnswerCorrection.agent_id == agent_id).all()
    }

    groups: dict[str, dict] = {}
    for m in flagged:
        q = questions.get(m.id)
        if not q:
            continue
        key = normalize_question(q.content)
        if not key or key in corrected_keys:
            continue
        g = groups.get(key)
        if not g:
            # flagged is newest-first, so the first hit carries the latest wording
            g = groups[key] = {
                "key": key,
                "question": q.content.replace("<user_query>", "").replace("</user_query>", "").strip()[:1000],
                "sample_answer": (m.content or "")[:1000],
                "count": 0,
                "last_asked_at": m.created_at.isoformat() if m.created_at else None,
                "message_ids": [],
            }
        g["count"] += 1
        if len(g["message_ids"]) < MAX_MESSAGE_IDS:
            g["message_ids"].append(m.id)

    items = sorted(groups.values(), key=lambda g: (g["count"], g["last_asked_at"] or ""), reverse=True)
    unanswered_total = sum(g["count"] for g in items)
    return {
        "days": days,
        "total_replies": total_replies,
        "unanswered": unanswered_total,
        "rate": round(unanswered_total / total_replies, 4) if total_replies else 0,
        "questions": items[:100],
    }


@router.post("/{agent_id}/unanswered/dismiss")
def dismiss_unanswered(agent_id: uuid.UUID, payload: DismissIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _owned_agent(db, agent_id, user)
    updated = _mark_messages(db, agent_id, payload.message_ids, DISMISSED)
    db.commit()
    return {"updated": updated}


@router.get("/{agent_id}/corrections")
def list_corrections(agent_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _owned_agent(db, agent_id, user)
    rows = (
        db.query(models.AnswerCorrection, models.KnowledgeBase.status)
        .outerjoin(models.KnowledgeBase, models.KnowledgeBase.id == models.AnswerCorrection.kb_id)
        .filter(models.AnswerCorrection.agent_id == agent_id)
        .order_by(models.AnswerCorrection.created_at.desc())
        .all()
    )
    return [_correction_out(c, status.value if status else None) for c, status in rows]


@router.post("/{agent_id}/corrections", status_code=201)
async def create_correction(agent_id: uuid.UUID, payload: CorrectionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    agent = _owned_agent(db, agent_id, user)
    kb = await _store_qa(db, agent, payload.question, payload.answer)
    correction = models.AnswerCorrection(
        agent_id=agent.id,
        kb_id=kb.id,
        question=payload.question.strip(),
        question_key=normalize_question(payload.question),
        answer=payload.answer.strip(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(correction)
    _mark_messages(db, agent.id, payload.message_ids, CORRECTED)
    db.commit()
    db.refresh(correction)
    return _correction_out(correction, kb.status.value)


@router.put("/{agent_id}/corrections/{correction_id}")
async def update_correction(
    agent_id: uuid.UUID,
    correction_id: uuid.UUID,
    payload: CorrectionIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    agent = _owned_agent(db, agent_id, user)
    correction = (
        db.query(models.AnswerCorrection)
        .filter(models.AnswerCorrection.id == correction_id, models.AnswerCorrection.agent_id == agent.id)
        .first()
    )
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    # Replace the knowledge source so the old wording leaves the index
    new_kb = await _store_qa(db, agent, payload.question, payload.answer)
    old_kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == correction.kb_id).first() if correction.kb_id else None
    correction.kb_id = new_kb.id
    correction.question = payload.question.strip()
    correction.question_key = normalize_question(payload.question)
    correction.answer = payload.answer.strip()
    correction.updated_at = datetime.now(timezone.utc)
    db.commit()
    if old_kb:
        await delete_kb_completely(db, old_kb, agent)
    db.refresh(correction)
    return _correction_out(correction, new_kb.status.value)


@router.delete("/{agent_id}/corrections/{correction_id}", status_code=204)
async def delete_correction(agent_id: uuid.UUID, correction_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    agent = _owned_agent(db, agent_id, user)
    correction = (
        db.query(models.AnswerCorrection)
        .filter(models.AnswerCorrection.id == correction_id, models.AnswerCorrection.agent_id == agent.id)
        .first()
    )
    if not correction:
        raise HTTPException(status_code=404, detail="Correction not found")
    kb = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == correction.kb_id).first() if correction.kb_id else None
    db.delete(correction)
    db.commit()
    if kb:
        await delete_kb_completely(db, kb, agent)
