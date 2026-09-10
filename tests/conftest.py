import os
import sys

import types

import pytest

import sqlalchemy


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_real_create_engine = sqlalchemy.create_engine


def _test_create_engine(_url, **_kwargs):
    return _real_create_engine("sqlite:///:memory:")


sqlalchemy.create_engine = _test_create_engine


@pytest.fixture
def anyio_backend():
    return "asyncio"

# Provide lightweight stubs for optional dependencies not installed in the test env.
if "redis" not in sys.modules:
    redis_module = types.ModuleType("redis")

    class _FakeRedis:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *_args, **_kwargs):
            return None

        def setex(self, *_args, **_kwargs):
            return None

        def delete(self, *_args, **_kwargs):
            return 0

        def close(self):
            return None

    def _from_url(*_args, **_kwargs):
        return _FakeRedis()

    redis_module.Redis = _FakeRedis
    redis_module.from_url = _from_url

    asyncio_module = types.ModuleType("redis.asyncio")
    asyncio_module.Redis = _FakeRedis
    redis_module.asyncio = asyncio_module
    sys.modules["redis"] = redis_module
    sys.modules["redis.asyncio"] = asyncio_module

if "slowapi" not in sys.modules:
    slowapi_module = types.ModuleType("slowapi")

    class _FakeLimiter:
        def __init__(self, **kwargs):
            self._key_prefix = kwargs.get("key_prefix")

        def limit(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    slowapi_module.Limiter = _FakeLimiter
    sys.modules["slowapi"] = slowapi_module

    util_module = types.ModuleType("slowapi.util")
    util_module.get_remote_address = lambda *_args, **_kwargs: "127.0.0.1"
    sys.modules["slowapi.util"] = util_module

if "supabase" not in sys.modules:
    supabase_module = types.ModuleType("supabase")

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

    def _create_client(*_args, **_kwargs):
        return _FakeClient()

    supabase_module.Client = _FakeClient
    supabase_module.create_client = _create_client
    sys.modules["supabase"] = supabase_module

if "litellm" not in sys.modules:
    litellm_module = types.ModuleType("litellm")

    def _completion(**_kwargs):
        raise RuntimeError("litellm is not installed")

    litellm_module.completion = _completion
    sys.modules["litellm"] = litellm_module

# pgvector fallback for sqlite tests — keep model clean (Vector only on Postgres)
# This keeps `pytest --sqlite` in-memory DB tests from failing on CREATE TABLE vector(1024)
if "pgvector.sqlalchemy" not in sys.modules:
    pgvector_module = types.ModuleType("pgvector")
    sqlalchemy_module = types.ModuleType("pgvector.sqlalchemy")
    from sqlalchemy import Text as _Text

    def _VectorFallback(dim):  # type: ignore
        return _Text()

    sqlalchemy_module.Vector = _VectorFallback  # type: ignore
    pgvector_module.sqlalchemy = sqlalchemy_module  # type: ignore
    sys.modules["pgvector"] = pgvector_module
    sys.modules["pgvector.sqlalchemy"] = sqlalchemy_module
else:
    # If pgvector is installed but we are on sqlite, patch Vector to Text for tests
    try:
        import pgvector.sqlalchemy as _pgv  # type: ignore

        from sqlalchemy import Text as _Text2

        _orig_vector = _pgv.Vector

        def _patched_vector(dim):  # type: ignore
            # Detect sqlite in-memory test run (DATABASE_URL is forced to sqlite above)
            if os.getenv("DATABASE_URL", "").startswith("sqlite"):
                return _Text2()
            return _orig_vector(dim)

        _pgv.Vector = _patched_vector  # type: ignore
    except Exception:
        pass
