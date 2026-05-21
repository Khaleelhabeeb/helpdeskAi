from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Optional

from sqlalchemy.orm import Session

from db import models
from services.redis_client import aredis_get_json, aredis_set_json, cache_key, redis_delete

CHAT_RUNTIME_CACHE_TTL_SECONDS = int(os.getenv("CHAT_RUNTIME_CACHE_TTL_SECONDS", "60"))


@dataclass(frozen=True)
class AgentRuntime:
    id: str
    user_id: int
    name: str
    instructions: str
    model: str
    retrieval_enabled: bool
    retrieval_top_k: int
    vector_store_namespace: Optional[str]


def _runtime_cache_key(agent_id: str, user_id: int) -> str:
    return cache_key("chat", "runtime", user_id, agent_id)


async def get_agent_runtime(db: Session, agent_id: str, user_id: int) -> Optional[AgentRuntime]:
    key = _runtime_cache_key(agent_id, user_id)
    cached = await aredis_get_json(key)
    if isinstance(cached, dict):
        try:
            return AgentRuntime(**cached)
        except TypeError:
            pass

    row = (
        db.query(models.Agent, models.AgentConfig)
        .outerjoin(models.AgentConfig, models.AgentConfig.agent_id == models.Agent.id)
        .filter(models.Agent.id == agent_id, models.Agent.user_id == user_id)
        .first()
    )
    if not row:
        return None

    agent, cfg = row
    runtime = AgentRuntime(
        id=str(agent.id),
        user_id=int(agent.user_id),
        name=agent.name,
        instructions=agent.instructions or "",
        model=agent.model,
        retrieval_enabled=bool(cfg.retrieval_enabled) if cfg else False,
        retrieval_top_k=int(cfg.retrieval_top_k) if cfg and cfg.retrieval_top_k else 4,
        vector_store_namespace=cfg.vector_store_namespace if cfg else None,
    )
    await aredis_set_json(key, asdict(runtime), CHAT_RUNTIME_CACHE_TTL_SECONDS)
    return runtime


def invalidate_agent_runtime(agent_id: str, user_id: Optional[int] = None) -> None:
    if user_id is not None:
        redis_delete(_runtime_cache_key(agent_id, user_id))
