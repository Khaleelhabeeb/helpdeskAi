"""Widget deployment/visitor token signing and abuse-signature detection."""

import hashlib
import hmac
import base64
import os
import time
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def _widget_secret() -> str:
    # Re-read env each time so tests can flip it
    return (os.getenv("WIDGET_SECRET") or os.getenv("JWT_SECRET") or "change-this-in-production").strip() or "change-this-in-production"


WIDGET_SECRET = _widget_secret()
TOKEN_EXPIRY_SECONDS = 300
VISITOR_TOKEN_EXPIRY_SECONDS = 3600 * 24 * 7  # visitor conversation lifetime


def _hmac_hex(payload: str) -> str:
    secret = _widget_secret()
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def generate_widget_token(deployment_id: str, expiry_seconds: int = TOKEN_EXPIRY_SECONDS) -> str:
    """Return a signed token as `deployment_id:expiry:signature`."""
    expiry = int(time.time()) + expiry_seconds
    payload = f"{deployment_id}:{expiry}"
    signature = _hmac_hex(payload)
    return f"{payload}:{signature}"


def verify_widget_token(token: str, deployment_id: str) -> Tuple[bool, Optional[str]]:
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False, "Invalid token format"
        
        token_deployment_id, expiry_str, signature = parts
        
        if token_deployment_id != deployment_id:
            return False, "Deployment ID mismatch"
        
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False, "Token expired"
        
        payload = f"{token_deployment_id}:{expiry_str}"
        expected_signature = _hmac_hex(payload)
        
        if not hmac.compare_digest(signature, expected_signature):
            return False, "Invalid signature"
        
        return True, None
    except Exception as e:
        return False, f"Token validation error: {str(e)}"


# Visitor payload is base64url-encoded then signed, so visitor_id may contain any char
VISITOR_TOKEN_VERSION = "v1"


def generate_visitor_token(
    deployment_id: str,
    conversation_id: str,
    visitor_id: str,
    expiry_seconds: int = VISITOR_TOKEN_EXPIRY_SECONDS,
) -> str:
    expiry = int(time.time()) + expiry_seconds
    raw = f"{deployment_id}:{conversation_id}:{visitor_id}:{expiry}"
    b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    sig = _hmac_hex(f"{VISITOR_TOKEN_VERSION}.{b64}")
    return f"{VISITOR_TOKEN_VERSION}.{b64}.{sig}"


def verify_visitor_token(
    token: str,
    deployment_id: str,
    conversation_id: str,
    visitor_id: str,
) -> Tuple[bool, Optional[str]]:
    try:
        if not token:
            return False, "Missing token"
        parts = token.split(".")
        if len(parts) != 3:
            return False, "Invalid visitor token format"
        ver, b64, sig = parts
        if ver != VISITOR_TOKEN_VERSION:
            return False, "Unsupported token version"
        expected_sig = _hmac_hex(f"{ver}.{b64}")
        if not hmac.compare_digest(sig, expected_sig):
            return False, "Invalid signature"
        padded = b64 + "=" * (-len(b64) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        # visitor_id may contain ':' so parse both ends; only the first two fields are
        # delimiter-free (deployment_id, conversation_id), expiry is after the last colon
        last_colon = raw.rfind(":")
        if last_colon == -1:
            return False, "Invalid payload"
        expiry_str = raw[last_colon + 1:]
        rest = raw[:last_colon]
        first = rest.find(":")
        second = rest.find(":", first + 1) if first != -1 else -1
        if first == -1 or second == -1:
            return False, "Invalid payload"
        token_deployment = rest[:first]
        token_conv = rest[first + 1:second]
        token_visitor = rest[second + 1:]
        if token_deployment != deployment_id:
            return False, "Deployment mismatch"
        if token_conv != conversation_id:
            return False, "Conversation mismatch"
        if token_visitor != visitor_id:
            return False, "Visitor mismatch"
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False, "Token expired"
        return True, None
    except Exception as e:
        return False, f"Visitor token validation error: {str(e)}"


def generate_visitor_token_for_deployment(
    deployment_id: str,
    conversation_id: str,
    visitor_id: str,
) -> str:
    return generate_visitor_token(deployment_id, conversation_id, visitor_id)


def get_rate_limit_key(deployment_id: str, visitor_id: str, ip: str, user_agent: str) -> str:
    ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
    return f"{deployment_id}:{ip}:{visitor_id}:{ua_hash}"


def detect_abuse_signature(
    deployment_id: str,
    visitor_id: str,
    ip: str,
    user_agent: str,
    message: str
) -> Tuple[bool, Optional[str]]:
    if len(message) > 10000:
        return True, "Message too long"

    suspicious_patterns = [
        "script>",
        "javascript:",
        "onerror=",
        "onclick=",
        "<iframe",
    ]
    message_lower = message.lower()
    for pattern in suspicious_patterns:
        if pattern in message_lower:
            return True, f"Suspicious pattern: {pattern}"
    
    if not user_agent or len(user_agent) < 10:
        return True, "Missing or invalid user agent"

    return False, None


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
