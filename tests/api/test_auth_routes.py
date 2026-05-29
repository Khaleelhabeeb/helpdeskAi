from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import auth as auth_routes


class DummySession:
    def __init__(self, access_token="access", refresh_token="refresh"):
        self.access_token = access_token
        self.refresh_token = refresh_token


class DummyUser:
    def __init__(self, user_id="user-1", email="user@example.com"):
        self.id = user_id
        self.email = email


class DummyResponse:
    def __init__(self, user=None, session=None):
        self.user = user
        self.session = session


class DummyAuthClient:
    def __init__(self, sign_up_response=None, sign_in_response=None, refresh_response=None, exchange_response=None):
        self._sign_up_response = sign_up_response
        self._sign_in_response = sign_in_response
        self._refresh_response = refresh_response
        self._exchange_response = exchange_response
        self.calls = []

    def sign_up(self, payload):
        self.calls.append(("sign_up", payload))
        return self._sign_up_response

    def sign_in_with_password(self, payload):
        self.calls.append(("sign_in", payload))
        return self._sign_in_response

    def refresh_session(self, payload):
        self.calls.append(("refresh", payload))
        if isinstance(self._refresh_response, Exception):
            raise self._refresh_response
        return self._refresh_response

    def exchange_code_for_session(self, payload):
        self.calls.append(("exchange", payload))
        return self._exchange_response


class DummySupabaseClient:
    def __init__(self, auth_client):
        self.auth = auth_client


class DummyDb:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        return None


def build_app():
    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/auth")
    return app


def test_supabase_config_missing_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    client = TestClient(build_app())
    response = client.get("/auth/supabase-config")

    assert response.status_code == 500, (
        "Expected missing Supabase env to return 500"
    )
    assert response.json() == {"detail": "Supabase config is missing"}, (
        "Expected missing Supabase env detail message"
    )


def test_supabase_config_returns_keys(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")

    client = TestClient(build_app())
    response = client.get("/auth/supabase-config")

    assert response.status_code == 200, "Expected supabase-config to succeed"
    assert response.json() == {
        "url": "https://example.supabase.co",
        "anon_key": "anon",
    }, "Expected supabase-config to return exact config values"


def test_signup_returns_tokens_and_message(monkeypatch):
    session = DummySession("access-1", "refresh-1")
    response_obj = DummyResponse(user=DummyUser("u1"), session=session)
    auth_client = DummyAuthClient(sign_up_response=response_obj)
    supabase_client = DummySupabaseClient(auth_client)

    captured = {}

    def fake_upsert(db, supabase_user_id, email):
        captured["args"] = (db, supabase_user_id, email)

    app = build_app()
    app.dependency_overrides[auth_routes.get_db] = lambda: DummyDb()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)
    monkeypatch.setattr(auth_routes, "upsert_local_user", fake_upsert)

    client = TestClient(app)
    response = client.post(
        "/auth/signup",
        json={"email": "User@Example.com", "password": "secret"},
    )

    assert response.status_code == 200, "Expected signup to succeed"
    assert response.json() == {
        "message": "User created successfully",
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "token_type": "bearer",
    }, "Expected signup to return tokens and message"
    assert captured["args"][1:] == ("u1", "user@example.com"), (
        "Expected upsert_local_user to be called with normalized email"
    )


def test_login_invalid_credentials(monkeypatch):
    response_obj = DummyResponse(user=None, session=None)
    auth_client = DummyAuthClient(sign_in_response=response_obj)
    supabase_client = DummySupabaseClient(auth_client)

    app = build_app()
    app.dependency_overrides[auth_routes.get_db] = lambda: DummyDb()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)

    client = TestClient(app)
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "bad"},
    )

    assert response.status_code == 401, "Expected invalid login to return 401"
    assert response.json() == {"detail": "Invalid credentials"}, (
        "Expected invalid login to return exact detail"
    )


def test_login_success_returns_tokens_and_user_type(monkeypatch):
    session = DummySession("access-2", "refresh-2")
    response_obj = DummyResponse(user=DummyUser("u2"), session=session)
    auth_client = DummyAuthClient(sign_in_response=response_obj)
    supabase_client = DummySupabaseClient(auth_client)

    class DbUser:
        user_type = "free"

    app = build_app()
    app.dependency_overrides[auth_routes.get_db] = lambda: DummyDb()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)
    monkeypatch.setattr(auth_routes, "upsert_local_user", lambda *_args: DbUser())

    client = TestClient(app)
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 200, "Expected login to succeed"
    assert response.json() == {
        "access_token": "access-2",
        "refresh_token": "refresh-2",
        "token_type": "bearer",
        "user_type": "free",
    }, "Expected login to return tokens and user_type"


def test_refresh_session_uses_fallback_payload(monkeypatch):
    session = DummySession("access-3", "refresh-3")
    response_obj = DummyResponse(session=session)

    auth_client = DummyAuthClient(refresh_response=RuntimeError("boom"))
    supabase_client = DummySupabaseClient(auth_client)

    def fake_refresh(payload):
        if isinstance(payload, str):
            raise RuntimeError("boom")
        return response_obj

    auth_client.refresh_session = fake_refresh

    app = build_app()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)

    client = TestClient(app)
    response = client.post("/auth/refresh", json={"refresh_token": "r1"})

    assert response.status_code == 200, "Expected refresh to succeed after fallback"
    assert response.json() == {
        "access_token": "access-3",
        "refresh_token": "refresh-3",
        "token_type": "bearer",
    }, "Expected refresh to return tokens"


def test_verify_auth_returns_user_info(monkeypatch):
    app = build_app()

    def fake_user():
        return DummyUser(user_id="u9", email="u9@example.com")

    app.dependency_overrides[auth_routes.verify_supabase_token] = fake_user

    client = TestClient(app)
    response = client.get("/auth/verify")

    assert response.status_code == 200, "Expected verify to succeed"
    assert response.json() == {
        "status": "valid",
        "user_id": "u9",
        "email": "u9@example.com",
    }, "Expected verify to return user info"
