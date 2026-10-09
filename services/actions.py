"""Custom API actions: validation, secret storage, tool schemas, and SSRF-safe execution."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import string
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import quote, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from db import models

logger = logging.getLogger(__name__)

ACTION_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,47}$")
PARAM_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,39}$")
HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
RESERVED_ACTION_NAMES = {"transfer_to_human"}
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
PARAM_TYPES = {"string", "number", "boolean"}
# Headers we never let owners set; httpx/our runtime own these
BLOCKED_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}
MAX_ACTIONS_PER_AGENT = 20
MAX_PARAMS = 15
MAX_RESPONSE_BYTES = 64 * 1024
MAX_RESULT_CHARS_FOR_LLM = 4000
HEADER_MASK = "••••••••"


def _is_prod() -> bool:
    return os.getenv("ENV") == "production"


def _allow_private_networks() -> bool:
    # Opt-in for local development against mock APIs; never honored in production
    return not _is_prod() and os.getenv("ACTIONS_ALLOW_PRIVATE_NETWORKS", "").lower() in {"1", "true", "yes"}


# ── Secret storage ────────────────────────────────────────────────────────────

def _fernet() -> Fernet:
    key = (os.getenv("ACTIONS_ENCRYPTION_KEY") or "").strip()
    if key:
        return Fernet(key.encode())
    seed = (os.getenv("WIDGET_SECRET") or os.getenv("JWT_SECRET") or "").strip()
    if not seed:
        if _is_prod():
            raise RuntimeError("ACTIONS_ENCRYPTION_KEY must be set in production")
        seed = "helpdeskai-dev-only-actions-key"
    derived = base64.urlsafe_b64encode(hashlib.sha256(f"actions:{seed}".encode()).digest())
    return Fernet(derived)


def encrypt_headers(headers: dict[str, str]) -> Optional[str]:
    if not headers:
        return None
    return _fernet().encrypt(json.dumps(headers).encode()).decode()


def decrypt_headers(blob: Optional[str]) -> dict[str, str]:
    if not blob:
        return {}
    try:
        data = json.loads(_fernet().decrypt(blob.encode()).decode())
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (InvalidToken, ValueError):
        logger.error("action_headers_decrypt_failed")
        return {}


def masked_headers(blob: Optional[str]) -> list[dict[str, str]]:
    return [{"name": k, "value": HEADER_MASK} for k in decrypt_headers(blob)]


# ── Validation (owner input) ─────────────────────────────────────────────────

class ActionValidationError(ValueError):
    pass


def url_placeholders(url: str) -> list[str]:
    return [name for _, name, _, _ in string.Formatter().parse(url) if name]


def validate_action_name(name: str) -> str:
    value = (name or "").strip().lower()
    if not ACTION_NAME_RE.match(value):
        raise ActionValidationError("Name must be 3–48 chars: lowercase letters, numbers, underscores; start with a letter")
    if value in RESERVED_ACTION_NAMES:
        raise ActionValidationError("That name is reserved")
    return value


def validate_parameters(params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(params) > MAX_PARAMS:
        raise ActionValidationError(f"At most {MAX_PARAMS} parameters")
    seen: set[str] = set()
    cleaned = []
    for p in params:
        name = str(p.get("name") or "").strip()
        if not PARAM_NAME_RE.match(name):
            raise ActionValidationError(f"Invalid parameter name: {name or '(empty)'}")
        if name in seen:
            raise ActionValidationError(f"Duplicate parameter: {name}")
        seen.add(name)
        ptype = str(p.get("type") or "string")
        if ptype not in PARAM_TYPES:
            raise ActionValidationError(f"Parameter {name}: type must be string, number, or boolean")
        cleaned.append({
            "name": name,
            "type": ptype,
            "description": str(p.get("description") or "").strip()[:300],
            "required": bool(p.get("required", True)),
        })
    return cleaned


def validate_url_template(url: str, params: list[dict[str, Any]]) -> str:
    value = (url or "").strip()
    try:
        placeholders = url_placeholders(value)
    except ValueError:
        raise ActionValidationError("URL has an unbalanced { or }")
    parsed = urlparse(value)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ActionValidationError("URL must start with https://")
    if parsed.scheme == "http" and _is_prod():
        raise ActionValidationError("URL must use https")
    if "{" in (parsed.netloc or ""):
        # The LLM must never choose where a request goes
        raise ActionValidationError("Placeholders are only allowed in the path or query, not the host")
    if parsed.username or parsed.password:
        raise ActionValidationError("Put credentials in headers, not the URL")
    known = {p["name"] for p in params}
    missing = [ph for ph in placeholders if ph not in known]
    if missing:
        raise ActionValidationError(f"URL uses undefined parameter(s): {', '.join(missing)}")
    return value[:2000]


def validate_headers(headers: list[dict[str, str]], existing_blob: Optional[str]) -> dict[str, str]:
    """Header values equal to the mask keep their stored value, so the UI never needs the secret."""
    existing = decrypt_headers(existing_blob)
    result: dict[str, str] = {}
    for h in headers[:20]:
        name = str(h.get("name") or "").strip()
        if not name:
            continue
        if not HEADER_NAME_RE.match(name) or name.lower() in BLOCKED_HEADERS:
            raise ActionValidationError(f"Header not allowed: {name}")
        value = str(h.get("value") or "")
        if value == HEADER_MASK:
            if name not in existing:
                raise ActionValidationError(f"Re-enter the value for header {name}")
            value = existing[name]
        if "\n" in value or "\r" in value:
            raise ActionValidationError(f"Invalid value for header {name}")
        result[name] = value[:2000]
    return result


# ── Runtime ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RuntimeAction:
    id: str
    name: str
    description: str
    method: str
    url: str
    parameters: list[dict[str, Any]] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 10


def to_runtime(action: models.AgentAction) -> RuntimeAction:
    return RuntimeAction(
        id=str(action.id),
        name=action.name,
        description=action.description,
        method=action.method,
        url=action.url,
        parameters=list(action.parameters or []),
        headers=decrypt_headers(action.headers_encrypted),
        timeout_seconds=max(1, min(int(action.timeout_seconds or 10), 30)),
    )


def load_runtime_actions(db: Session, agent_id: uuid.UUID | str) -> list[RuntimeAction]:
    rows = (
        db.query(models.AgentAction)
        .filter(models.AgentAction.agent_id == agent_id, models.AgentAction.enabled.is_(True))
        .order_by(models.AgentAction.created_at)
        .limit(MAX_ACTIONS_PER_AGENT)
        .all()
    )
    return [to_runtime(r) for r in rows]


def tool_schema(action: RuntimeAction) -> dict:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in action.parameters:
        properties[p["name"]] = {"type": p["type"], "description": p.get("description") or p["name"]}
        if p.get("required"):
            required.append(p["name"])
    return {
        "type": "function",
        "function": {
            "name": action.name,
            "description": action.description[:1000],
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _coerce(value: Any, ptype: str) -> Any:
    if ptype == "number":
        if isinstance(value, bool):
            raise ValueError("expected a number")
        num = float(value)
        return int(num) if num.is_integer() else num
    if ptype == "boolean":
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "1", "yes"}:
            return True
        if str(value).lower() in {"false", "0", "no"}:
            return False
        raise ValueError("expected true or false")
    return str(value)[:1000]


def build_request(action: RuntimeAction, arguments: dict[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    """Returns (url, query_params, json_body). Raises ValueError with an LLM-readable message."""
    args = arguments if isinstance(arguments, dict) else {}
    values: dict[str, Any] = {}
    for p in action.parameters:
        name = p["name"]
        if name in args and args[name] is not None and args[name] != "":
            try:
                values[name] = _coerce(args[name], p["type"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Parameter '{name}': {exc}")
        elif p.get("required"):
            raise ValueError(f"Missing required parameter '{name}'")

    placeholders = set(url_placeholders(action.url))
    path_values = {k: quote(str(values.get(k, "")), safe="") for k in placeholders}
    url = action.url.format(**path_values)
    rest = {k: v for k, v in values.items() if k not in placeholders}

    if action.method in ("GET", "DELETE"):
        return url, (rest or None), None
    return url, None, rest


async def _assert_public_host(host: str, port: int) -> None:
    if _allow_private_networks():
        return
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Could not resolve the API host")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified or not ip.is_global
        ):
            raise ValueError("The API host resolves to a private or internal address")


@dataclass
class ActionResult:
    ok: bool
    status: Optional[int]
    body: str
    error: Optional[str] = None
    duration_ms: float = 0.0

    def for_llm(self) -> str:
        if self.error:
            return json.dumps({"ok": False, "error": self.error})
        body = self.body
        if len(body) > MAX_RESULT_CHARS_FOR_LLM:
            body = body[:MAX_RESULT_CHARS_FOR_LLM] + "…(truncated)"
        return json.dumps({"ok": self.ok, "status": self.status, "data": body})


async def execute_action(action: RuntimeAction, arguments: dict[str, Any]) -> ActionResult:
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        url, query, body = build_request(action, arguments)
        parsed = urlparse(url)
        await _assert_public_host(parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80))
    except ValueError as exc:
        return ActionResult(ok=False, status=None, body="", error=str(exc))

    headers = {"User-Agent": "HelpdeskAI-Actions/1.0", "Accept": "application/json, text/plain;q=0.9", **action.headers}
    try:
        # Fresh client: no redirects (a redirect could point at an internal host), tight timeout
        async with httpx.AsyncClient(follow_redirects=False, timeout=action.timeout_seconds) as client:
            async with client.stream(action.method, url, params=query, json=body, headers=headers) as resp:
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        chunks.append(chunk[: max(0, MAX_RESPONSE_BYTES - (size - len(chunk)))])
                        break
                    chunks.append(chunk)
                text = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
                ok = 200 <= resp.status_code < 300
                return ActionResult(ok=ok, status=resp.status_code, body=text, duration_ms=(loop.time() - started) * 1000)
    except httpx.TimeoutException:
        return ActionResult(ok=False, status=None, body="", error="The API timed out", duration_ms=(loop.time() - started) * 1000)
    except httpx.HTTPError as exc:
        logger.info("action_http_error action=%s err=%s", action.name, type(exc).__name__)
        return ActionResult(ok=False, status=None, body="", error="Could not reach the API", duration_ms=(loop.time() - started) * 1000)


ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Optional[str]]]


def make_executor(actions: list[RuntimeAction], *, log_context: str = "") -> ToolExecutor:
    """Returns an executor for the LLM tool loop. Unknown names return None (caller handles them)."""
    by_name = {a.name: a for a in actions}

    async def _execute(name: str, arguments: dict[str, Any]) -> Optional[str]:
        action = by_name.get(name)
        if not action:
            return None
        result = await execute_action(action, arguments)
        logger.info(
            "action_executed %s action=%s ok=%s status=%s ms=%.0f",
            log_context, name, result.ok, result.status, result.duration_ms,
        )
        return result.for_llm()

    return _execute


ACTIONS_SYSTEM_HINT = (
    "You can call tools to look things up or take actions for the user. "
    "Only call a tool when the user's request needs it, ask for any missing required details first, "
    "and base your answer on the tool result. If a tool fails, say so briefly and offer another way to help. "
    "Never reveal tool names, URLs, or raw API responses."
)
