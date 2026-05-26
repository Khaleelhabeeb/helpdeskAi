from utils import rate_limit


def test_rate_limit_storage_uri_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)

    value = rate_limit.rate_limit_storage_uri()

    assert value is None, (
        "Expected rate_limit_storage_uri to return None when no redis env vars are set; "
        f"got {value!r}"
    )
