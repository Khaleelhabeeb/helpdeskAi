import hashlib
from typing import Any


def _as_string(value: Any) -> str:
    return str(value)


def agent_runtime(agent_id: Any) -> str:
    return f"agent_runtime:{_as_string(agent_id)}"


def auth_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"auth:token:{digest}"


def dashboard_summary(user_id: Any) -> str:
    return f"dashboard_summary:{_as_string(user_id)}"


def model_catalog() -> str:
    return "models:available"


def widget_config(deployment_id: Any) -> str:
    return f"widget_config:{_as_string(deployment_id)}"


def widget_rate_limit(
    prefix: str,
    deployment_id: str,
    ip: str,
    visitor_id: str,
    window_start: int,
) -> str:
    raw_key = f"{deployment_id}:{ip}:{visitor_id}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"{prefix}:widget:{deployment_id}:{digest}:{window_start}"
