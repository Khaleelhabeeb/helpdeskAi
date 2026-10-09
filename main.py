import asyncio as _asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from api import human_agent as human_agent_api
from api import models as model_catalog
from api import owner_human_agents, owner_team
from api.agents import agents, chat, knowledge_base, settings, widget_deployment
from api.analytics import analytics
from api.auth import auth, password_reset
from api.scrape import scrape
from api.storage import storage, upload
from api.users import users
from db.database import engine
from services.email_provider import get_sent_emails
from services.groq_client import aclose_groq_clients, close_groq_clients
from services.handoff_sweeper import sweeper_loop
from services.http_client import close_http_clients
from services.redis_client import close_redis_clients
from utils.jwt import get_current_user as _get_current_user_for_debug
from utils.rate_limit import create_limiter

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("helpdeskai.api")
limiter = create_limiter()
is_prod = os.getenv("ENV") == "production"

_sweeper_stop: _asyncio.Event | None = None
_sweeper_task: _asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sweeper_stop, _sweeper_task
    _sweeper_stop = _asyncio.Event()
    try:
        _sweeper_task = _asyncio.create_task(sweeper_loop(_sweeper_stop))
        logger.info("handoff_sweeper_started")
    except Exception:
        logger.exception("handoff_sweeper_start_failed")
    yield
    try:
        if _sweeper_stop is not None:
            _sweeper_stop.set()
        if _sweeper_task is not None:
            await _asyncio.wait_for(_sweeper_task, timeout=5)
    except Exception:
        pass
    await close_http_clients(close_all=True)
    await close_redis_clients(close_all=True)
    close_groq_clients()
    await aclose_groq_clients()


app = FastAPI(
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
    lifespan=lifespan,
)
frontend_url = os.getenv("FRONTEND_URL")
_cors_origins = [o.strip() for o in (frontend_url or "").split(",") if o.strip()]
if not _cors_origins and not is_prod:
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
if is_prod and not _cors_origins:
    logger.warning("CORS origins empty in production (FRONTEND_URL unset): browser API calls will be blocked")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    if not request.url.path.startswith(("/health", "/healthz")):
        logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


@app.get("/health", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
def health_check():
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readiness_check():
    """Liveness vs readiness split: verifies DB connectivity + migrations."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            # Migration gate: lifecycle columns must exist
            try:
                conn.execute(text("SELECT last_visitor_at FROM conversations LIMIT 1"))
            except Exception:
                return JSONResponse(
                    status_code=503,
                    content={"status": "migrating", "detail": "DB migrations pending"},
                )
        return {"status": "ready"}
    except Exception as exc:
        logger.warning("readyz_failed err=%s", exc)
        return JSONResponse(status_code=503, content={"status": "not_ready"})


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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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
        headers={"X-Request-ID": request_id},
        content={"detail": exc.errors(), "request_id": request_id, "code": "validation_error"},
    )


class PublicWidgetCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/public/widget/"):
            if request.method == "OPTIONS":
                origin = request.headers.get("origin")
                headers = {
                    "Access-Control-Allow-Origin": origin or "*",
                    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Widget-Version",
                }
                return Response(status_code=200, headers=headers)

            response = await call_next(request)
            origin = request.headers.get("origin")
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Widget-Version"
            return response

        return await call_next(request)


class CachedStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        path = str(args[0]) if args else ""
        # Hashed build files can be immutable; raw widget files must not be (we just fixed a handoff loop)
        if ("widget-loader" in path or "widget-panel" in path):
            if "/build/" in path:
                if any(x in path for x in [".js", ".html", ".css"]):
                    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                # Raw dev files — short cache so fixes propagate immediately
                response.headers["Cache-Control"] = "public, max-age=60"
        elif path.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            response.headers["Cache-Control"] = "public, max-age=86400"
        else:
            response.headers["Cache-Control"] = "public, max-age=60"
        return response


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else (["*"] if not is_prod else []),
    allow_credentials=bool(_cors_origins),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Widget-Version"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(PublicWidgetCORSMiddleware)

# ── Routes ──────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth")
app.include_router(password_reset.router, prefix="/auth")

app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(settings.router, prefix="/agents", tags=["Agent Settings"])
app.include_router(widget_deployment.router, prefix="/agents", tags=["Widget Deployment"])
app.include_router(widget_deployment.public_router, prefix="/public/widget", tags=["Public Widget"])
app.include_router(widget_deployment.help_router, prefix="/public/help", tags=["Public Help Page"])
app.include_router(upload.router, prefix="/knowledge", tags=["Knowledge Upload"])
app.include_router(knowledge_base.router, prefix="/kb", tags=["Knowledge Base"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(storage.router, prefix="/users", tags=["Storage"])
app.include_router(scrape.router, prefix="/scrape", tags=["Scrape"])
app.include_router(analytics.router, tags=["KPI"])
app.include_router(model_catalog.router, prefix="/models", tags=["Models"])

# Human handoff
app.include_router(owner_human_agents.router, prefix="/owner/human-agents", tags=["Owner — Human Agents"])
app.include_router(owner_team.router, prefix="/owner/team", tags=["Owner — Team"])
app.include_router(human_agent_api.auth_router, prefix="/human-agent/auth", tags=["Human Agent — Auth"])
app.include_router(human_agent_api.router, prefix="/human-agent", tags=["Human Agent"])


# Debug mock-email outbox: 404 in production, owner auth otherwise, HTML stripped
@app.get("/debug/emails", include_in_schema=False)
def debug_emails(user=Depends(_get_current_user_for_debug)):
    if os.getenv("ENV") == "production":
        raise HTTPException(status_code=404)
    # Only allow when explicitly enabled (defense in depth for S3)
    if os.getenv("ENABLE_DEBUG_EMAILS", "0") != "1":
        raise HTTPException(status_code=404)
    return {"emails": [
        {
            "to_email": e.to_email,
            "subject": e.subject,
            "provider": e.provider,
            "sent_at": e.sent_at.isoformat(),
            # Never return the HTML body (it can contain token links)
            "has_html": bool(e.html_content),
        }
        for e in get_sent_emails()[-50:]
    ]}


app.mount("/static", CachedStaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
