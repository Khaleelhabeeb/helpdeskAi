"""
Transactional email abstraction — Brevo implementation (§5 and §2).

Converted from Go EmailService sample provided by user.
Primary provider is Brevo via direct HTTPS POST to https://api.brevo.com/v3/smtp/email
(avoiding the old sib_api_v3_sdk for explicit timeout/wrapping control).
Mock fallback is retained for tests/local dev when BREVO_API_KEY is missing
or EMAIL_PROVIDER=mock is forced.

Usage:
    from services.email_provider import send_transactional_email
    send_transactional_email(to_email="a@b.com", subject="hi", html_content="<p>hi</p>")

All typed helpers funnel through send_transactional_email so provider swap is one place.
Env:
    BREVO_API_KEY       – required for real sends (from .env)
    BREVO_SENDER_EMAIL  – verified sender, default no-reply@helpdeskai.web.app
    BREVO_SENDER_NAME   – default HelpDeskAI
    FRONTEND_URL        – for invite / reopen links
    EMAIL_PROVIDER      – mock|brevo (default: brevo if BREVO_API_KEY set, else mock)
"""
from __future__ import annotations

import html as _html
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

# ── In-memory outbox (mock + debug) ─────────────────────────────────────────

@dataclass
class SentEmail:
    to_email: str
    to_name: Optional[str]
    subject: str
    html_content: str  # stored as wrapped HTML (what Brevo would receive after wrap)
    text_content: Optional[str] = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = "mock"

_SENT_OUTBOX: List[SentEmail] = []  # process-global store for tests + /debug/emails


def get_sent_emails() -> List[SentEmail]:
    return list(_SENT_OUTBOX)


def clear_sent_emails() -> None:
    _SENT_OUTBOX.clear()


# ── Brevo service (ported from Go) ──────────────────────────────────────────

class BrevoEmailService:
    """Direct HTTP Brevo sender, mirroring Go EmailService."""

    def __init__(self, api_key: str, sender_email: str, sender_name: str, frontend_url: str):
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.frontend_url = frontend_url.rstrip("/")
        # httpx client is lazy-imported to avoid hard dependency in tests
        self._http = None

    def _get_http(self):
        if self._http is None:
            try:
                import httpx
                self._http = httpx.Client(timeout=10.0)
            except Exception as exc:
                # fallback to stdlib http.client if httpx unavailable
                logger.warning("httpx unavailable, falling back to urllib: %s", exc)
                self._http = None
        return self._http

    def wrap_html(self, content: str) -> str:
        year = datetime.now().year
        # HelpDeskAI system design — minimal, zinc/black, Inter
        return f"""
<html>
<body style="font-family:Inter, -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif; background:#f8f8f7; padding:32px 16px; color:#18181b; margin:0;">
    <div style="max-width:560px; margin:0 auto; background:#ffffff; padding:32px; border-radius:20px; border:1px solid #e4e4e7; box-shadow:0 1px 2px rgba(0,0,0,0.04);">
        <div style="text-align:center; margin-bottom:24px;">
            <div style="display:inline-block; background:#09090b; color:#fafafa; padding:8px 16px; border-radius:9999px; font-weight:800; font-size:13px; letter-spacing:-0.02em; line-height:1;">{self.sender_name}</div>
            <div style="margin-top:10px; font-size:10px; color:#71717a; letter-spacing:0.12em; text-transform:uppercase; font-weight:700;">frelo.com.ng · HelpDeskAI workspace</div>
        </div>
        {content}
        <hr style="border:0; border-top:1px solid #e4e4e7; margin:28px 0;">
        <p style="font-size:11px; color:#a1a1aa; text-align:center; line-height:1.5; margin:0;">&copy; {year} {self.sender_name} via frelo.com.ng. All rights reserved.<br/>This email was sent from a verified domain. If you didn't request it, you can ignore it.</p>
    </div>
    <p style="font-size:11px; color:#a1a1aa; text-align:center; margin-top:16px;">Need help? Reply in the HelpDeskAI dashboard — email replies aren't monitored.</p>
</body>
</html>"""

    def send_brevo(self, to: str, name: str, subject: str, html_content: str) -> bool:
        if not self.api_key:
            logger.info("Brevo: BREVO_API_KEY not set, skipping email to=%s subject=%s", to, subject)
            return True  # treat as success so invite flow not blocked in dev without key

        # Safety: never attempt real Brevo delivery to obvious fake/test domains
        _fake_domains = ("@example.com", "@example.org", "@test.com", "@invalid")
        if any(to.lower().endswith(d) for d in _fake_domains):
            logger.info("brevo_fake_domain_skip to=%s subject=%s (mocked)", to, subject)
            return True

        name = (name or "").strip() or to
        wrapped = self.wrap_html(html_content)

        body = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": to, "name": name}],
            "subject": subject,
            "htmlContent": wrapped,
        }
        payload = json.dumps(body)
        http_client = self._get_http()

        # Prefer httpx, fallback to urllib
        if http_client is not None:
            try:
                import httpx  # type: ignore
                resp = http_client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    content=payload,
                    headers={
                        "accept": "application/json",
                        "api-key": self.api_key,
                        "content-type": "application/json",
                    },
                )
                if resp.status_code >= 400:
                    logger.error("brevo API error (status %d): %s to=%s subject=%s", resp.status_code, resp.text[:500], to, subject)
                    return False
                logger.info("brevo_email_sent to=%s subject=%s", to, subject)
                return True
            except Exception as exc:
                logger.exception("brevo_send_failed to=%s subject=%s err=%s", to, subject, exc)
                return False
        else:
            # stdlib fallback
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                "https://api.brevo.com/v3/smtp/email",
                data=payload.encode("utf-8"),
                headers={
                    "accept": "application/json",
                    "api-key": self.api_key,
                    "content-type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status >= 400:
                        body_text = resp.read().decode("utf-8", errors="ignore")[:500]
                        logger.error("brevo API error (status %d): %s to=%s", resp.status, body_text, to)
                        return False
                    logger.info("brevo_email_sent to=%s subject=%s", to, subject)
                    return True
            except urllib.error.HTTPError as exc:
                try:
                    body_text = exc.read().decode("utf-8", errors="ignore")[:500]
                except Exception:
                    body_text = str(exc)
                logger.error("brevo API error (status %d): %s to=%s", exc.code, body_text, to)
                return False
            except Exception as exc:
                logger.exception("brevo_send_failed to=%s subject=%s err=%s", to, subject, exc)
                return False


_brevo_singleton: Optional[BrevoEmailService] = None


def _get_brevo_service() -> Optional[BrevoEmailService]:
    global _brevo_singleton
    # Re-read env each time so tests can flip EMAIL_PROVIDER/BREVO_API_KEY
    api_key = (os.getenv("BREVO_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        return None
    sender_email = (os.getenv("BREVO_SENDER_EMAIL") or os.getenv("SENDER_EMAIL") or "no-reply@frelo.com.ng").strip()
    sender_name = (os.getenv("BREVO_SENDER_NAME") or os.getenv("SENDER_NAME") or "HelpDeskAI").strip() or "HelpDeskAI"
    frontend_url = (os.getenv("FRONTEND_URL") or "http://localhost:3000").strip()
    # Cache singleton but bust if key/email/name changed
    if _brevo_singleton is None or _brevo_singleton.api_key != api_key or _brevo_singleton.sender_email != sender_email or _brevo_singleton.sender_name != sender_name:
        _brevo_singleton = BrevoEmailService(api_key, sender_email, sender_name, frontend_url)
    else:
        # keep frontend_url fresh without recreating
        _brevo_singleton.frontend_url = frontend_url.rstrip("/")
    return _brevo_singleton


def _should_mock() -> bool:
    provider = (os.getenv("EMAIL_PROVIDER") or "").lower().strip()
    # Explicit mock always wins (used by pytest / local dev without key)
    if provider in ("mock", "log"):
        return True
    # If no API key, must mock
    if not (os.getenv("BREVO_API_KEY") or "").strip():
        return True
    # If provider explicitly brevo, use real
    if provider == "brevo":
        return False
    # Default: if key exists and provider empty/unset, use real (user has verified domain)
    # but force mock when running under pytest to avoid real network calls
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return True
    if provider == "":
        return False
    # Unknown provider -> mock
    return True


def send_transactional_email(
    *,
    to_email: str,
    subject: str,
    html_content: str,
    to_name: Optional[str] = None,
    text_content: Optional[str] = None,
) -> bool:
    """
    Unified sender. `html_content` is the *inner* content (will be wrapped via
    Brevo's wrapHTML). For mock, we store the wrapped version as well so
    /debug/emails preview matches what Brevo would send.
    """
    # Always store a wrapped preview for debugging, even when mocked
    svc = _get_brevo_service()
    # Decide mock vs real
    if _should_mock() or svc is None:
        # For mock, wrap as well so preview is faithful, but mark provider mock
        wrapped = svc.wrap_html(html_content) if svc else html_content
        entry = SentEmail(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html_content=wrapped,
            text_content=text_content,
            provider="mock",
        )
        _SENT_OUTBOX.append(entry)
        logger.info("mock_email_sent to=%s subject=%s outbox=%d", to_email, subject, len(_SENT_OUTBOX))
        return True

    # Real Brevo path
    ok = svc.send_brevo(to=to_email, name=to_name or "", subject=subject, html_content=html_content)
    # Also keep a copy in outbox for /debug/emails auditing
    wrapped = svc.wrap_html(html_content)
    _SENT_OUTBOX.append(SentEmail(
        to_email=to_email, to_name=to_name, subject=subject,
        html_content=wrapped, text_content=text_content,
        provider="brevo" if ok else "brevo-failed",
    ))
    if not ok:
        logger.warning("brevo_send_returned_false to=%s subject=%s — stored as brevo-failed", to_email, subject)
    return ok


# ── Typed helpers (port of Go helpers + handoff specifics) ───────────────────

def send_invite_email(*, to_email: str, invite_token: str, inviter_email: str | None = None) -> bool:
    frontend = (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
    invite_link = f"{frontend}/human-agent/accept-invite?token={invite_token}"
    subject = f"You're invited to join HelpDeskAI as a support agent"
    inviter_line = f"<p style=\"color:#52525b; line-height:1.6; margin:0 0 12px;\"><strong style=\"color:#18181b;\">{_html.escape(inviter_email)}</strong> invited you to join their support team as a human agent.</p>" if inviter_email else "<p style=\"color:#52525b; line-height:1.6; margin:0 0 12px;\">You were invited to join a support team as a human agent.</p>"
    html_inner = f"""
<h2 style="color:#18181b; font-size:20px; font-weight:800; letter-spacing:-0.02em; margin:0 0 12px;">You're invited to HelpDeskAI</h2>
{inviter_line}
<p style="color:#52525b; line-height:1.6; margin:0 0 16px;">Click the button below to set your password and activate your account. This link expires in 7 days.</p>
<div style="margin: 24px 0; text-align: center;">
    <a href="{invite_link}" style="background:#09090b; color:#fafafa; padding:12px 22px; text-decoration:none; border-radius:9999px; font-weight:700; font-size:14px; display:inline-block; letter-spacing:-0.01em;">Accept invite &amp; set password</a>
</div>
<div style="background:#fafafa; border:1px solid #e4e4e7; border-radius:12px; padding:12px 14px; margin:16px 0;">
    <p style="font-size:11px; color:#71717a; margin:0 0 4px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase;">Invite link</p>
    <p style="font-size:12px; color:#52525b; word-break:break-all; margin:0;"><a href="{invite_link}" style="color:#18181b; font-weight:600; text-decoration:underline; text-underline-offset:3px;">{invite_link}</a></p>
</div>
<p style="font-size:12px; color:#a1a1aa; margin:8px 0 0;">If you didn't expect this invite, you can safely ignore this email.</p>
"""
    return send_transactional_email(to_email=to_email, to_name=to_email.split("@")[0], subject=subject, html_content=html_inner)


def send_queued_fallback_email(*, to_email: str, conversation_id: str, agent_name: str | None = None) -> bool:
    frontend = (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
    reopen_link = f"{frontend}/?conversation={conversation_id}"
    subject = "We got your message — we'll follow up by email"
    agent_label = _html.escape(agent_name) if agent_name else "our team"
    html_inner = f"""
<div style="display:flex; align-items:center; gap:8px; margin:0 0 12px;">
    <span style="display:inline-grid; place-items:center; width:28px; height:28px; border-radius:9999px; background:#09090b; color:#fafafa; font-size:14px;">✓</span>
    <h2 style="color:#18181b; font-size:18px; font-weight:800; letter-spacing:-0.02em; margin:0;">We got your message</h2>
</div>
<p style="color:#52525b; line-height:1.6; margin:0 0 12px;">Thanks for reaching out. No agent is online right now, but <strong style="color:#18181b;">{agent_label}</strong> will follow up by email as soon as possible.</p>
<div style="background:#fafafa; border:1px solid #e4e4e7; border-radius:14px; padding:16px; margin:16px 0; text-align:center;">
    <p style="color:#52525b; font-size:13px; margin:0 0 12px;">You can reopen the chat to continue — your history is saved.</p>
    <a href="{reopen_link}" style="background:#09090b; color:#fafafa; padding:11px 20px; text-decoration:none; border-radius:9999px; font-weight:700; font-size:13px; display:inline-block;">Reopen chat</a>
    <p style="font-size:11px; color:#a1a1aa; margin:10px 0 0; word-break:break-all;"><a href="{reopen_link}" style="color:#52525b; text-decoration:underline; text-underline-offset:3px;">{reopen_link}</a></p>
</div>
<p style="font-size:11px; color:#a1a1aa; margin:0; font-family:ui-monospace, SFMono-Regular, Menlo, monospace;">Conversation ID: {conversation_id}</p>
"""
    return send_transactional_email(to_email=to_email, to_name=None, subject=subject, html_content=html_inner)


def send_human_reply_email(
    *,
    to_email: str,
    reply_text: str,
    conversation_id: str,
    agent_name: str | None = None,
    from_name: str | None = None,
) -> bool:
    frontend = (os.getenv("FRONTEND_URL") or "http://localhost:3000").rstrip("/")
    reopen_link = f"{frontend}/?conversation={conversation_id}"
    subject = f"Reply from {from_name or agent_name or 'Support'} — HelpDeskAI"
    sender = _html.escape(from_name or agent_name or "A teammate")
    safe_reply = _html.escape(reply_text).replace("\n", "<br/>")
    html_inner = f"""
<p style="color:#71717a; font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; margin:0 0 8px;">New reply from your support team</p>
<h2 style="color:#18181b; font-size:18px; font-weight:800; letter-spacing:-0.02em; margin:0 0 12px;">{sender} replied</h2>
<div style="background:#ffffff; border:1px solid #e4e4e7; border-radius:14px; padding:16px; margin:12px 0; line-height:1.6; color:#18181b; font-size:14px;">{safe_reply}</div>
<div style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:10px 12px; margin:12px 0;">
    <p style="font-size:12px; color:#991b1b; margin:0; font-weight:600;">Reply in the chat to continue — email replies aren't monitored in this version.</p>
</div>
<div style="margin: 20px 0; text-align: center;">
    <a href="{reopen_link}" style="background:#09090b; color:#fafafa; padding:11px 20px; text-decoration:none; border-radius:9999px; font-weight:700; font-size:13px; display:inline-block;">Open chat</a>
    <p style="font-size:11px; color:#a1a1aa; margin:8px 0 0; word-break:break-all;"><a href="{reopen_link}" style="color:#52525b; text-decoration:underline; text-underline-offset:3px;">{reopen_link}</a></p>
</div>
<p style="font-size:11px; color:#a1a1aa; margin:0; font-family:ui-monospace, SFMono-Regular, Menlo, monospace;">Conversation: {conversation_id}</p>
"""
    return send_transactional_email(to_email=to_email, to_name=None, subject=subject, html_content=html_inner)


# ── Additional Go-ported helpers (optional, for future use) ──────────────────

def send_email_verification_otp(*, to_email: str, to_name: str, otp: str) -> bool:
    svc = _get_brevo_service()
    sender = svc.sender_name if svc else "HelpDeskAI"
    subject = f"Verify your email - {sender}"
    html_inner = f"""
<h2 style="color:#18181b; font-size:18px; font-weight:800; margin:0 0 12px;">Hello {_html.escape(to_name)},</h2>
<p style="color:#52525b; line-height:1.6;">Welcome to <b style="color:#18181b;">{_html.escape(sender)}</b> via frelo.com.ng! Please verify your email address to activate your account.</p>
<p style="color:#52525b;">Use the following 6-digit verification code:</p>
<div style="margin: 24px 0; text-align: center;">
    <div style="display:inline-block; background:#09090b; color:#fafafa; padding:14px 28px; border-radius:14px; font-size:30px; font-weight:800; letter-spacing:6px; border:1px solid #18181b;">
        {_html.escape(otp)}
    </div>
</div>
<p style="color:#52525b; font-size:13px;">This code is valid for 10 minutes.</p>
<div style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:10px 12px; margin-top:12px;">
    <p style="font-size:12px; color:#991b1b; margin:0; font-weight:700;">Do not share this code with anyone.</p>
</div>
"""
    return send_transactional_email(to_email=to_email, to_name=to_name, subject=subject, html_content=html_inner)


def send_password_reset_otp(*, to_email: str, to_name: str, otp: str) -> bool:
    svc = _get_brevo_service()
    sender = svc.sender_name if svc else "HelpDeskAI"
    subject = f"Security Code: {otp} for {sender}"
    html_inner = f"""
<h2 style="color:#18181b; font-size:18px; font-weight:800; margin:0 0 8px;">Password Reset Code</h2>
<p style="color:#52525b; margin:0 0 12px;">Hello <strong style="color:#18181b;">{_html.escape(to_name)}</strong>,</p>
<p style="color:#52525b; line-height:1.6;">We received a request to reset your password. Use the following 6-digit code to proceed:</p>
<div style="margin: 24px 0; text-align: center;">
    <div style="display:inline-block; background:#09090b; color:#fafafa; padding:14px 28px; border-radius:14px; font-size:30px; font-weight:800; letter-spacing:6px; border:1px solid #18181b;">
        {_html.escape(otp)}
    </div>
</div>
<p style="color:#52525b; font-size:13px;">This code is valid for 10 minutes. If you didn't request this, please ignore this email.</p>
<div style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:10px 12px; margin-top:12px;">
    <p style="font-size:12px; color:#991b1b; margin:0; font-weight:700;">Do not share this code with anyone.</p>
</div>
"""
    return send_transactional_email(to_email=to_email, to_name=to_name, subject=subject, html_content=html_inner)


def send_custom_email(*, to_email: str, to_name: str, subject: str, content: str) -> bool:
    escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", "<br/>")
    html_inner = f"""<h2 style="color:#18181b; font-size:18px; font-weight:800; margin:0 0 8px;">{_html.escape(subject)}</h2>
<p style="color:#52525b; margin:0 0 12px;">Hello <strong style="color:#18181b;">{_html.escape(to_name)}</strong>,</p>
<div style="background:#fafafa; border:1px solid #e4e4e7; border-radius:12px; padding:14px; margin: 12px 0; white-space: pre-wrap; line-height:1.6; color:#18181b;">{escaped}</div>
"""
    return send_transactional_email(to_email=to_email, to_name=to_name, subject=subject, html_content=html_inner)
