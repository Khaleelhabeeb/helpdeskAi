"""Groq client factories: sync `Groq` and per-event-loop `AsyncGroq` singletons.

Model ids are normalised (legacy `groq/` prefix stripped) before use.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Optional

from utils.env import get_secret

logger = logging.getLogger(__name__)

_GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "30"))
_GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "2"))

# Singletons — protected by lock for thread safety (uvicorn workers)
_lock = threading.Lock()
_sync_client: Optional[object] = None
_sync_client_key: Optional[str] = None
# Async clients are per-event-loop (like services/http_client) for scalable concurrency
_async_clients: dict[tuple[int, int], tuple[object, str]] = {}


def get_groq_api_key() -> Optional[str]:
    """Resolve GROQ_API_KEY from the process env or .env."""
    return get_secret("GROQ_API_KEY", prefixes=("gsk_",))


def normalize_groq_model(model: str) -> str:
    """
    Strip the legacy `groq/` prefix so DB values like `groq/llama-3.1-8b-instant`
    map to Groq's native model ids.
    """
    if not model:
        return model
    cleaned = model.strip()
    if cleaned.startswith("groq/"):
        return cleaned[len("groq/") :]
    return cleaned


def _require_api_key() -> str:
    key = get_groq_api_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return key


def get_groq_client():
    """
    Thread-safe singleton Groq sync client.
    Re-created automatically if API key rotates.
    """
    global _sync_client, _sync_client_key

    api_key = _require_api_key()

    # Fast path without lock
    if _sync_client is not None and _sync_client_key == api_key:
        return _sync_client

    with _lock:
        if _sync_client is not None and _sync_client_key == api_key:
            return _sync_client

        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError(
                "groq package not installed. Run `uv add groq` or `pip install groq`"
            ) from exc

        # Groq SDK handles its own httpx.Client pooling internally.
        client = Groq(
            api_key=api_key,
            timeout=_GROQ_TIMEOUT_SECONDS,
            max_retries=_GROQ_MAX_RETRIES,
        )
        _sync_client = client
        _sync_client_key = api_key
        logger.debug("groq_sync_client_initialized timeout=%s retries=%s", _GROQ_TIMEOUT_SECONDS, _GROQ_MAX_RETRIES)
        return client


def get_async_groq_client():
    """
    Per-event-loop AsyncGroq client, keyed by thread + loop id so the underlying
    httpx.AsyncClient is never shared across event loops.
    """
    api_key = _require_api_key()

    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        # No running loop (e.g. sync context) — fallback to thread id only
        loop_id = 0

    key = (threading.get_ident(), loop_id)

    # Fast path
    entry = _async_clients.get(key)
    if entry is not None and entry[1] == api_key:
        return entry[0]

    with _lock:
        entry = _async_clients.get(key)
        if entry is not None and entry[1] == api_key:
            return entry[0]

        try:
            from groq import AsyncGroq
        except ImportError as exc:
            raise RuntimeError(
                "groq package not installed. Run `uv add groq` or `pip install groq`"
            ) from exc

        client = AsyncGroq(
            api_key=api_key,
            timeout=_GROQ_TIMEOUT_SECONDS,
            max_retries=_GROQ_MAX_RETRIES,
        )
        _async_clients[key] = (client, api_key)
        logger.debug(
            "groq_async_client_initialized thread=%s loop=%s timeout=%s retries=%s",
            threading.get_ident(),
            loop_id,
            _GROQ_TIMEOUT_SECONDS,
            _GROQ_MAX_RETRIES,
        )
        return client


def close_groq_clients() -> None:
    global _sync_client, _sync_client_key
    with _lock:
        if _sync_client is not None:
            try:
                close_fn = getattr(_sync_client, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception:
                logger.debug("groq_sync_close_failed", exc_info=True)
            finally:
                _sync_client = None
                _sync_client_key = None


async def aclose_groq_clients(close_all: bool = True) -> None:
    # Snapshot outside the lock so it is not held across the awaits below
    if close_all:
        with _lock:
            clients = list(_async_clients.items())
            _async_clients.clear()
    else:
        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
        except RuntimeError:
            loop_id = 0
        key = (threading.get_ident(), loop_id)
        with _lock:
            entry = _async_clients.pop(key, None)
            clients = [(key, entry)] if entry else []

    for _key, entry in clients:
        if entry is None:
            continue
        client, _ = entry
        try:
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                maybe_coro = close_fn()
                if hasattr(maybe_coro, "__await__"):
                    await maybe_coro
        except Exception:
            logger.debug("groq_async_close_failed", exc_info=True)
