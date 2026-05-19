import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def rate_limit_storage_uri() -> str | None:
    return (os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL") or "").strip() or None


def create_limiter() -> Limiter:
    return Limiter(
        key_func=get_remote_address,
        storage_uri=rate_limit_storage_uri(),
        headers_enabled=True,
        swallow_errors=True,
        in_memory_fallback_enabled=True,
        key_prefix=(os.getenv("RATE_LIMIT_REDIS_PREFIX") or "helpdeskai:ratelimit").strip(":"),
    )
