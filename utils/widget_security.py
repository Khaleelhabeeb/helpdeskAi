"""
Widget security utilities for token signing and validation
"""
import hashlib
import hmac
import os
import time
from typing import Optional, Tuple


WIDGET_SECRET = os.getenv("WIDGET_SECRET", "change-this-in-production")
TOKEN_EXPIRY_SECONDS = 300  # 5 minutes


def generate_widget_token(deployment_id: str, expiry_seconds: int = TOKEN_EXPIRY_SECONDS) -> str:
    """
    Generate a signed token for widget deployment
    
    Args:
        deployment_id: The deployment ID
        expiry_seconds: Token validity duration in seconds
    
    Returns:
        Signed token string in format: deployment_id:expiry:signature
    """
    expiry = int(time.time()) + expiry_seconds
    payload = f"{deployment_id}:{expiry}"
    signature = hmac.new(
        WIDGET_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_widget_token(token: str, deployment_id: str) -> Tuple[bool, Optional[str]]:
    """
    Verify a signed widget token
    
    Args:
        token: The token to verify
        deployment_id: Expected deployment ID
    
    Returns:
        Tuple of (is_valid, error_message)
    """
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
        expected_signature = hmac.new(
            WIDGET_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return False, "Invalid signature"
        
        return True, None
    except Exception as e:
        return False, f"Token validation error: {str(e)}"


def get_rate_limit_key(deployment_id: str, visitor_id: str, ip: str, user_agent: str) -> str:
    """
    Generate composite rate limit key including UA hash for abuse detection
    
    Args:
        deployment_id: Widget deployment ID
        visitor_id: Visitor identifier
        ip: Client IP address
        user_agent: User agent string
    
    Returns:
        Composite rate limit key
    """
    ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
    return f"{deployment_id}:{ip}:{visitor_id}:{ua_hash}"


def detect_abuse_signature(
    deployment_id: str,
    visitor_id: str,
    ip: str,
    user_agent: str,
    message: str
) -> Tuple[bool, Optional[str]]:
    """
    Detect potential abuse patterns
    
    Args:
        deployment_id: Widget deployment ID
        visitor_id: Visitor identifier
        ip: Client IP address
        user_agent: User agent string
        message: Message content
    
    Returns:
        Tuple of (is_abuse, reason)
    """
    # Check for honeypot indicators
    if len(message) > 10000:
        return True, "Message too long"
    
    # Check for suspicious patterns
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
    
    # Check for missing or suspicious UA
    if not user_agent or len(user_agent) < 10:
        return True, "Missing or invalid user agent"
    
    return False, None
