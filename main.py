import logging
import os
import resource
import sys
import threading
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from api import models as model_catalog
from api.agents import agents, chat, knowledge_base, settings, widget_deployment
from api.analystics import analytic
from api.auth import auth, password_reset
from api.scrape import scrape
from api.storage import storage, upload
from api.users import users
from db.database import engine
from services.rate_limit import limiter_storage_options
from services.redis_client import (
    close_async_redis,
    close_sync_redis,
    get_sync_redis,
    redis_configured,
    redis_url,
)
from utils.jwt import get_current_user


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("helpdeskai.api")
is_prod = os.getenv("ENV") == "production"
_active_requests = 0
_active_requests_lock = threading.Lock()


limiter = Limiter(key_func=get_remote_address, **limiter_storage_options())


def _log_startup_diagnostics() -> None:
    logger.info(
        "startup pid=%s python=%s env=%s db_pool=%s redis_configured=%s celery_broker_configured=%s",
        os.getpid(),
        sys.version.split()[0],
        os.getenv("ENV", ""),
        engine.pool.status(),
        redis_configured(),
        bool(os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL")),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _log_startup_diagnostics()
    try:
        yield
    finally:
        await close_async_redis()
        close_sync_redis()


app = FastAPI(
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    global _active_requests
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()
    response = None
    with _active_requests_lock:
        _active_requests += 1
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        with _active_requests_lock:
            _active_requests -= 1
        if not request.url.path.startswith(("/health", "/healthz")):
            status_code = response.status_code if response is not None else 500
            logger.info(
                "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )


@app.get("/health", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
def health_check():
    return {"status": "ok"}


def _rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage if sys.platform == "darwin" else usage * 1024)


def _cpu_percent_sample(interval_seconds: float = 0.05) -> float:
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    time.sleep(interval_seconds)
    wall_delta = max(time.perf_counter() - wall_start, 1e-9)
    cpu_delta = time.process_time() - cpu_start
    return round((cpu_delta / wall_delta) * 100, 2)


@app.get("/healthz/resources", include_in_schema=False)
def resource_health(user=Depends(get_current_user)):
    if getattr(user, "user_type", "") != "admin":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden"},
        )

    redis_queue_depth = None
    redis_ping = False
    redis = get_sync_redis()
    if redis is not None:
        try:
            redis_ping = bool(redis.ping())
            redis_queue_depth = int(redis.llen(os.getenv("CELERY_DEFAULT_QUEUE", "celery")))
        except Exception:
            logger.warning("resource_health_redis_failed", exc_info=True)

    with _active_requests_lock:
        active_requests = _active_requests

    return {
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "env": os.getenv("ENV", ""),
        "rss_bytes": _rss_bytes(),
        "cpu_percent_sample": _cpu_percent_sample(),
        "thread_count": threading.active_count(),
        "active_requests": active_requests,
        "db_pool": engine.pool.status(),
        "redis_configured": redis_configured(),
        "redis_url_present": bool(redis_url()),
        "redis_ping": redis_ping,
        "celery_queue_depth": redis_queue_depth,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    logger.exception(
        "unhandled_exception request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers={"X-Request-ID": request_id},
        content={"detail": "Internal server error", "request_id": request_id},
    )

# Custom exception handler for 422 validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Extract form data safely
    try:
        body_str = str(exc.body) if exc.body else "No body"
    except Exception:
        body_str = "Could not serialize body"
    if len(body_str) > 2000:
        body_str = f"{body_str[:2000]}...<truncated>"
    
    request_id = getattr(request.state, "request_id", "-")
    logger.warning(
        "validation_error request_id=%s method=%s path=%s errors=%s body=%s",
        request_id,
        request.method,
        request.url.path,
        exc.errors(),
        body_str,
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

class PublicWidgetCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/public/widget/"):
            if request.method == "OPTIONS":
                origin = request.headers.get("origin")
                headers = {
                    "Access-Control-Allow-Origin": origin or "*",
                    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                }
                return Response(status_code=200, headers=headers)
            
            response = await call_next(request)
            origin = request.headers.get("origin")
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            return response
            
        return await call_next(request)

# rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PublicWidgetCORSMiddleware)


app.include_router(auth.router, prefix="/auth")
app.include_router(password_reset.router, prefix="/auth")

app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(settings.router, prefix="/agents", tags=["Agent Settings"])
app.include_router(widget_deployment.router, prefix="/agents", tags=["Widget Deployment"])
app.include_router(widget_deployment.public_router, prefix="/public/widget", tags=["Public Widget"])
app.include_router(upload.router, prefix="/knowledge", tags=["Knowledge Upload"])
app.include_router(knowledge_base.router, prefix="/kb", tags=["Knowledge Base"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(users.router, prefix="/users", tags=["users"]) 
app.include_router(storage.router, prefix="/users", tags=["Storage"])
app.include_router(scrape.router, prefix="/scrape", tags=["Scrape"])
app.include_router(analytic.router, tags=["KPI"])
app.include_router(model_catalog.router, prefix="/models", tags=["Models"])
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    reload_enabled = os.getenv("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=reload_enabled)
