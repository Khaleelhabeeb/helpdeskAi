from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import password_reset


class DummyAuthClient:
    def __init__(self):
        self.calls = []

    def sign_in_with_otp(self, payload):
        # New OTP alias: capture payload
        self.calls.append(payload)

    def reset_password_email(self, email, options=None):
        # Legacy fallback should not be called anymore
        self.calls.append(("reset_password_email", email, options))


class DummySupabaseClient:
    def __init__(self, auth_client):
        self.auth = auth_client


def build_app():
    app = FastAPI()
    app.include_router(password_reset.router, prefix="/auth")
    return app


def test_forgot_password_returns_generic_message(monkeypatch):
    auth_client = DummyAuthClient()
    supabase_client = DummySupabaseClient(auth_client)

    monkeypatch.setattr(password_reset, "get_supabase_client", lambda: supabase_client)
    monkeypatch.setattr(password_reset, "FRONTEND_URL", "https://app.example.com")

    client = TestClient(build_app())
    response = client.post("/auth/forgot-password", json={"email": "User@Example.com"})

    assert response.status_code == 200, "Expected forgot-password to succeed"
    assert response.json() == {
        "message": "Check your email for a magic link to sign in. It expires in a few minutes."
    }, "Expected forgot-password to return OTP generic message"
    # Should now call sign_in_with_otp with normalized email and OTP redirect
    assert auth_client.calls[0]["email"] == "user@example.com"
    assert auth_client.calls[0]["options"]["email_redirect_to"] == "https://app.example.com/auth/callback"


def test_reset_password_returns_gone():
    client = TestClient(build_app())
    response = client.post("/auth/reset-password", json={"token": "t", "new_password": "password123"})

    assert response.status_code == 410, "Expected reset-password to return 410"
    assert response.json() == {
        "detail": "Password authentication is removed. Use POST /auth/otp/request with your email to receive a magic link. Google sign-in still works via Supabase OAuth."
    }, "Expected reset-password to return deprecation detail"
