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
    def __init__(self, sign_up_response=None, sign_in_response=None, refresh_response=None, exchange_response=None, otp_response=None, verify_response=None):
        self._sign_up_response = sign_up_response
        self._sign_in_response = sign_in_response
        self._refresh_response = refresh_response
        self._exchange_response = exchange_response
        self._otp_response = otp_response
        self._verify_response = verify_response
        self.calls = []

    def sign_up(self, payload):
        self.calls.append(("sign_up", payload))
        if isinstance(self._sign_up_response, Exception):
            raise self._sign_up_response
        return self._sign_up_response

    def sign_in_with_password(self, payload):
        self.calls.append(("sign_in", payload))
        return self._sign_in_response

    def sign_in_with_otp(self, payload):
        self.calls.append(("otp_request", payload))
        if isinstance(self._otp_response, Exception):
            raise self._otp_response
        return self._otp_response if self._otp_response is not None else {}

    def verify_otp(self, payload):
        self.calls.append(("otp_verify", payload))
        if isinstance(self._verify_response, Exception):
            raise self._verify_response
        return self._verify_response

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
    # Password signup is now disabled — should return 410 with OTP guidance
    app = build_app()
    client = TestClient(app)
    response = client.post(
        "/auth/signup",
        json={"email": "User@Example.com", "password": "secret"},
    )

    assert response.status_code == 410, "Expected signup to return 410 Gone (password flow disabled)"
    assert "otp/request" in response.json()["detail"].lower(), "Expected 410 detail to point to OTP flow"


def test_signup_rate_limit_returns_429(monkeypatch):
    # Password signup is disabled regardless of rate limits — legacy endpoint always 410
    app = build_app()
    client = TestClient(app)
    response = client.post(
        "/auth/signup",
        json={"email": "User@Example.com", "password": "secret"},
    )

    assert response.status_code == 410, "Expected signup to return 410 Gone"


def test_login_invalid_credentials(monkeypatch):
    # Password login is disabled — should return 410
    app = build_app()
    client = TestClient(app)
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "bad"},
    )

    assert response.status_code == 410, "Expected login to return 410 Gone (password flow disabled)"
    assert "otp/request" in response.json()["detail"].lower()


def test_login_success_returns_tokens_and_user_type(monkeypatch):
    # Password login disabled — even valid credentials return 410
    app = build_app()
    client = TestClient(app)
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 410, "Expected login to return 410 Gone"


def test_otp_request_sends_email_and_normalizes(monkeypatch):
    auth_client = DummyAuthClient(otp_response={})
    supabase_client = DummySupabaseClient(auth_client)

    app = build_app()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)
    monkeypatch.setattr(auth_routes, "FRONTEND_URL", "https://app.example.com")

    client = TestClient(app)
    response = client.post("/auth/otp/request", json={"email": "User@Example.com"})

    assert response.status_code == 200, "Expected otp/request to succeed"
    assert response.json() == {
        "message": "Check your email for a magic link to sign in. It expires in a few minutes."
    }
    # Verify normalized email and redirect_to
    assert auth_client.calls[0][1]["email"] == "user@example.com"
    assert auth_client.calls[0][1]["options"]["email_redirect_to"] == "https://app.example.com/auth/callback"


def test_otp_request_rate_limit(monkeypatch):
    auth_client = DummyAuthClient(otp_response=RuntimeError("429 Too Many Requests"))
    supabase_client = DummySupabaseClient(auth_client)

    app = build_app()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)

    client = TestClient(app)
    response = client.post("/auth/otp/request", json={"email": "user@example.com"})

    assert response.status_code == 429, "Expected otp/request rate limit to return 429"


def test_otp_verify_success_returns_tokens(monkeypatch):
    session = DummySession("access-otp", "refresh-otp")
    response_obj = DummyResponse(user=DummyUser("u-otp", "user@example.com"), session=session)
    auth_client = DummyAuthClient(verify_response=response_obj)
    supabase_client = DummySupabaseClient(auth_client)

    class DbUser:
        user_type = "free"

    app = build_app()
    app.dependency_overrides[auth_routes.get_db] = lambda: DummyDb()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)
    monkeypatch.setattr(auth_routes, "upsert_local_user", lambda *_args: DbUser())

    client = TestClient(app)
    response = client.post("/auth/otp/verify", json={"email": "user@example.com", "token": "123456"})

    assert response.status_code == 200, "Expected otp/verify to succeed"
    assert response.json() == {
        "access_token": "access-otp",
        "refresh_token": "refresh-otp",
        "token_type": "bearer",
        "user_type": "free",
    }
    assert auth_client.calls[0][0] == "otp_verify"
    assert auth_client.calls[0][1]["email"] == "user@example.com"
    assert auth_client.calls[0][1]["token"] == "123456"


def test_otp_verify_invalid_code_returns_401(monkeypatch):
    auth_client = DummyAuthClient(verify_response=RuntimeError("invalid token"))
    supabase_client = DummySupabaseClient(auth_client)

    app = build_app()
    app.dependency_overrides[auth_routes.get_db] = lambda: DummyDb()
    monkeypatch.setattr(auth_routes, "get_supabase_client", lambda: supabase_client)

    client = TestClient(app)
    response = client.post("/auth/otp/verify", json={"email": "user@example.com", "token": "bad"})

    assert response.status_code == 401, "Expected invalid otp to return 401"


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
