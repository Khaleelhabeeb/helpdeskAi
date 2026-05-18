import json
import logging
import os
from typing import Any

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)

DEFAULT_CACHE_PREFIX = "helpdeskai:cache"
DEFAULT_RATE_LIMIT_PREFIX = "helpdeskai:rl"
REDIS_TIMEOUT_SECONDS = 0.5

_async_client: AsyncRedis | None = None
_sync_client: Redis | None = None


def redis_url() -> str | None:
    value = os.getenv("REDIS_URL", "").strip()
    return value or None


def redis_configured() -> bool:
    return redis_url() is not None


def cache_prefix() -> str:
    return os.getenv("CACHE_REDIS_PREFIX", DEFAULT_CACHE_PREFIX).strip() or DEFAULT_CACHE_PREFIX


def rate_limit_prefix() -> str:
    return os.getenv("RATE_LIMIT_REDIS_PREFIX", DEFAULT_RATE_LIMIT_PREFIX).strip() or DEFAULT_RATE_LIMIT_PREFIX


def _client_options() -> dict[str, Any]:
    return {
        "decode_responses": True,
        "socket_connect_timeout": REDIS_TIMEOUT_SECONDS,
        "socket_timeout": REDIS_TIMEOUT_SECONDS,
        "ssl_cert_reqs": "required",
    }


def get_sync_redis() -> Redis | None:
    global _sync_client
    url = redis_url()
    if not url:
        return None
    if _sync_client is None:
        _sync_client = Redis.from_url(url, **_client_options())
    return _sync_client


def get_async_redis() -> AsyncRedis | None:
    global _async_client
    url = redis_url()
    if not url:
        return None
    if _async_client is None:
        _async_client = AsyncRedis.from_url(url, **_client_options())
    return _async_client


def close_sync_redis() -> None:
    global _sync_client
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None


async def close_async_redis() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None


def cache_key(name: str) -> str:
    return f"{cache_prefix()}:{name}"


def cache_get_json(name: str) -> Any | None:
    client = get_sync_redis()
    if client is None:
        return None
    try:
        value = client.get(cache_key(name))
    except RedisError:
        logger.warning("redis_cache_get_failed key=%s", name, exc_info=True)
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def cache_set_json(name: str, value: Any, ttl_seconds: int) -> None:
    client = get_sync_redis()
    if client is None:
        return
    try:
        client.setex(cache_key(name), ttl_seconds, json.dumps(value, default=str))
    except RedisError:
        logger.warning("redis_cache_set_failed key=%s", name, exc_info=True)


def cache_delete(name: str) -> None:
    client = get_sync_redis()
    if client is None:
        return
    try:
        client.delete(cache_key(name))
    except RedisError:
        logger.warning("redis_cache_delete_failed key=%s", name, exc_info=True)


async def acache_get_json(name: str) -> Any | None:
    client = get_async_redis()
    if client is None:
        return None
    try:
        value = await client.get(cache_key(name))
    except RedisError:
        logger.warning("redis_cache_get_failed key=%s", name, exc_info=True)
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


async def acache_set_json(name: str, value: Any, ttl_seconds: int) -> None:
    client = get_async_redis()
    if client is None:
        return
    try:
        await client.setex(cache_key(name), ttl_seconds, json.dumps(value, default=str))
    except RedisError:
        logger.warning("redis_cache_set_failed key=%s", name, exc_info=True)
