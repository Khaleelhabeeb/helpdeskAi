import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from celery import Celery

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()


DEFAULT_REDIS_URL = "redis://localhost:6379/0"
CELERY_TASK_MODULES = ["services.ingest_tasks", "services.retention_tasks"]


def _redis_url() -> str:
    return os.getenv("REDIS_URL", DEFAULT_REDIS_URL).strip() or DEFAULT_REDIS_URL


def _with_rediss_ssl_param(url: str) -> str:
    value = (url or "").strip()
    if not value.startswith("rediss://"):
        return value

    parsed = urlparse(value)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("ssl_cert_reqs", os.getenv("CELERY_SSL_CERT_REQS", "CERT_NONE"))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _celery_broker_url() -> str:
    return _with_rediss_ssl_param(os.getenv("CELERY_BROKER_URL") or _redis_url())


def _celery_result_backend_url() -> str:
    return _with_rediss_ssl_param(os.getenv("CELERY_RESULT_BACKEND") or _redis_url())


BROKER_URL = _celery_broker_url()
RESULT_BACKEND_URL = _celery_result_backend_url()

# Celery may read these environment variables directly; normalize them first.
os.environ["CELERY_BROKER_URL"] = BROKER_URL
os.environ["CELERY_RESULT_BACKEND"] = RESULT_BACKEND_URL


celery_app = Celery(
    "helpdeskai",
    broker=BROKER_URL,
    backend=RESULT_BACKEND_URL,
    include=CELERY_TASK_MODULES,
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "900")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "840")),
    worker_prefetch_multiplier=int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")),
    broker_connection_retry_on_startup=True,
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
    result_backend_transport_options={"ssl_cert_reqs": ssl.CERT_NONE},
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "3600")),
)
