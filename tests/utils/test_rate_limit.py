import os

from utils import rate_limit


def test_rate_limit_storage_uri_prefers_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)

    value = rate_limit.rate_limit_storage_uri()

    assert value == "redis://localhost:6379/0", (
        "Expected rate_limit_storage_uri to return REDIS_URL when set; "
        f"got {value!r}"
    )


def test_create_limiter_uses_custom_prefix(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REDIS_PREFIX", "custom:ratelimit:")

    limiter = rate_limit.create_limiter()

    assert getattr(limiter, "_key_prefix", None) == "custom:ratelimit", (
        "Expected Limiter to normalize key prefix by trimming colons; "
        f"got {getattr(limiter, '_key_prefix', None)!r}"
    )
