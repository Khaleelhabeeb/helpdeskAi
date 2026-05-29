from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import password_reset


class DummyAuthClient:
    def __init__(self):
        self.calls = []

    def reset_password_email(self, email, options=None):
        self.calls.append((email, options))


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
        "message": "If that email exists, a password reset link has been sent"
    }, "Expected forgot-password to return generic message"
    assert auth_client.calls == [
        ("user@example.com", {"redirect_to": "https://app.example.com/reset-password"})
    ], "Expected reset_password_email to be called with normalized email and redirect"


def test_reset_password_returns_gone():
    client = TestClient(build_app())
    response = client.post("/auth/reset-password", json={"token": "t", "new_password": "password123"})

    assert response.status_code == 410, "Expected reset-password to return 410"
    assert response.json() == {
        "detail": "Password reset is handled by Supabase Auth. Use the Supabase recovery session on the frontend to update the password."
    }, "Expected reset-password to return deprecation detail"
