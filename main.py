import logging
import os
import time
import uuid

from fastapi import FastAPI, Request, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.agents import agents, chat, knowledge_base, settings, widget_deployment
from api.auth import auth, password_reset
from api.scrape import scrape
from api.storage import storage, upload
from api.users import users
from api import models as model_catalog
from db.database import Base, engine
from api.analystics import analytic
from fastapi.staticfiles import StaticFiles
from services.http_client import close_http_clients
from services.redis_client import close_redis_clients
from utils.rate_limit import create_limiter


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("helpdeskai.api")
limiter = create_limiter()
is_prod = os.getenv("ENV") == "production"
app = FastAPI(
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)
frontend_url = os.getenv("FRONTEND_URL")


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
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(PublicWidgetCORSMiddleware)


@app.on_event("shutdown")
async def close_shared_clients():
    await close_http_clients(close_all=True)
    await close_redis_clients(close_all=True)


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
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
