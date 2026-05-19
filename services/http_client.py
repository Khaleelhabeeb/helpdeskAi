import os
import asyncio
import threading

import httpx


_async_clients: dict[tuple[int, int], httpx.AsyncClient] = {}


def default_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=float(os.getenv("HTTP_CONNECT_TIMEOUT_SECONDS", "5")),
        read=float(os.getenv("HTTP_READ_TIMEOUT_SECONDS", "30")),
        write=float(os.getenv("HTTP_WRITE_TIMEOUT_SECONDS", "30")),
        pool=float(os.getenv("HTTP_POOL_TIMEOUT_SECONDS", "5")),
    )


def default_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=int(os.getenv("HTTP_MAX_CONNECTIONS", "50")),
        max_keepalive_connections=int(os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "20")),
        keepalive_expiry=float(os.getenv("HTTP_KEEPALIVE_EXPIRY_SECONDS", "30")),
    )


async def get_async_http_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    key = (threading.get_ident(), id(loop))
    client = _async_clients.get(key)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(timeout=default_timeout(), limits=default_limits())
        _async_clients[key] = client
    return client


async def close_http_clients(close_all: bool = False) -> None:
    if close_all:
        clients = list(_async_clients.items())
    else:
        loop = asyncio.get_running_loop()
        key = (threading.get_ident(), id(loop))
        client = _async_clients.get(key)
        clients = [(key, client)] if client else []

    for key, client in clients:
        if not client.is_closed:
            await client.aclose()
        _async_clients.pop(key, None)
