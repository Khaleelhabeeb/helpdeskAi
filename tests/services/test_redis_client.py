import os

from services import redis_client


def test_cache_key_normalizes_prefix_and_parts(monkeypatch):
    monkeypatch.setenv("CACHE_REDIS_PREFIX", "helpdeskai:")

    key = redis_client.cache_key("a", "", None, "b")

    assert key == "helpdeskai:a:b", (
        "Expected cache_key to trim empty parts and normalize prefix; "
        f"got {key!r}"
    )


def test_redis_get_json_returns_none_without_client(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)

    value = redis_client.redis_get_json("missing")

    assert value is None, (
        "Expected redis_get_json to return None when redis is not configured; "
        f"got {value!r}"
    )
