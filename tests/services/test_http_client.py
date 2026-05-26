import pytest

from services import http_client


@pytest.mark.anyio
async def test_get_async_http_client_is_cached_per_loop():
    client1 = await http_client.get_async_http_client()
    client2 = await http_client.get_async_http_client()

    assert client1 is client2, (
        "Expected get_async_http_client to return the same client per loop"
    )
    assert client1.is_closed is False, "Expected async client to be open"


def test_default_timeout_uses_env_values(monkeypatch):
    monkeypatch.setenv("HTTP_CONNECT_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("HTTP_READ_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("HTTP_WRITE_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("HTTP_POOL_TIMEOUT_SECONDS", "4")

    timeout = http_client.default_timeout()

    assert timeout.connect == 1.0, f"Expected connect timeout 1.0, got {timeout.connect}"
    assert timeout.read == 2.0, f"Expected read timeout 2.0, got {timeout.read}"
    assert timeout.write == 3.0, f"Expected write timeout 3.0, got {timeout.write}"
    assert timeout.pool == 4.0, f"Expected pool timeout 4.0, got {timeout.pool}"


def test_default_limits_uses_env_values(monkeypatch):
    monkeypatch.setenv("HTTP_MAX_CONNECTIONS", "11")
    monkeypatch.setenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "7")
    monkeypatch.setenv("HTTP_KEEPALIVE_EXPIRY_SECONDS", "9")

    limits = http_client.default_limits()

    assert limits.max_connections == 11, (
        "Expected max_connections to reflect env var; "
        f"got {limits.max_connections}"
    )
    assert limits.max_keepalive_connections == 7, (
        "Expected max_keepalive_connections to reflect env var; "
        f"got {limits.max_keepalive_connections}"
    )
    assert limits.keepalive_expiry == 9.0, (
        "Expected keepalive_expiry to reflect env var; "
        f"got {limits.keepalive_expiry}"
    )
