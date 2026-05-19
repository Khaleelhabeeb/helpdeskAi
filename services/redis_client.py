import json
import logging
import os
import asyncio
import threading
from functools import lru_cache
from typing import Any, Optional

import redis
from redis import Redis
from redis.asyncio import Redis as AsyncRedis


logger = logging.getLogger(__name__)
_async_clients: dict[tuple[int, int], AsyncRedis] = {}


def _redis_url() -> Optional[str]:
    return (os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL") or "").strip() or None


def _key_prefix() -> str:
    return (os.getenv("CACHE_REDIS_PREFIX") or "helpdeskai").strip().strip(":")


def cache_key(*parts: object) -> str:
    clean_parts = [str(part).strip(":") for part in parts if part is not None and str(part) != ""]
    return ":".join([_key_prefix(), *clean_parts])


@lru_cache(maxsize=1)
def get_redis() -> Optional[Redis]:
    url = _redis_url()
    if not url:
        return None
    try:
        return redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "2")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "2")),
            health_check_interval=30,
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
        )
    except Exception:
        logger.exception("redis_client_init_failed")
        return None


def get_async_redis() -> Optional[AsyncRedis]:
    url = _redis_url()
    if not url:
        return None
    try:
        loop = asyncio.get_running_loop()
        key = (threading.get_ident(), id(loop))
        client = _async_clients.get(key)
        if client is None:
            client = AsyncRedis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "2")),
                socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "2")),
                health_check_interval=30,
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
            )
            _async_clients[key] = client
        return client
    except Exception:
        logger.exception("async_redis_client_init_failed")
        return None


def redis_get_json(key: str) -> Optional[Any]:
    client = get_redis()
    if not client:
        return None
    try:
        value = client.get(key)
        return json.loads(value) if value else None
    except Exception:
        logger.warning("redis_get_failed key=%s", key, exc_info=True)
        return None


def redis_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        logger.warning("redis_set_failed key=%s", key, exc_info=True)


def redis_delete(*keys: str) -> None:
    client = get_redis()
    if not client or not keys:
        return
    try:
        client.delete(*keys)
    except Exception:
        logger.warning("redis_delete_failed keys=%s", keys, exc_info=True)


async def aredis_get_json(key: str) -> Optional[Any]:
    client = get_async_redis()
    if not client:
        return None
    try:
        value = await client.get(key)
        return json.loads(value) if value else None
    except Exception:
        logger.warning("async_redis_get_failed key=%s", key, exc_info=True)
        return None


async def aredis_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = get_async_redis()
    if not client:
        return
    try:
        await client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        logger.warning("async_redis_set_failed key=%s", key, exc_info=True)


async def close_redis_clients(close_all: bool = False) -> None:
    if close_all:
        clients = list(_async_clients.items())
    else:
        loop = asyncio.get_running_loop()
        key = (threading.get_ident(), id(loop))
        client = _async_clients.get(key)
        clients = [(key, client)] if client else []

    for key, async_client in clients:
        await async_client.aclose()
        _async_clients.pop(key, None)

    sync_client = get_redis()
    if close_all and sync_client:
        sync_client.close()
