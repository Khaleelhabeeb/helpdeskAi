from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.users import users as user_routes
from db import models
from utils import jwt


class FakeUser:
    def __init__(self, user_id=1, user_type="free"):
        self.id = user_id
        self.user_type = user_type
        self.credits_remaining = 12
        self.last_reset_date = datetime(2024, 1, 1)

    def get_max_credits(self):
        return 999999


class FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self._first = first_result
        self._all = all_result or []

    def filter(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def group_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all

    def first(self):
        return self._first


class FakeDb:
    def __init__(self, user_id, agent_usage=None):
        self.user_id = user_id
        self.agent_usage = agent_usage or []
        self.settings_by_user = {}
        self.added = []
        self.deleted = []

    def query(self, *args):
        if len(args) == 1 and args[0] is models.UserSettings:
            return FakeQuery(first_result=self.settings_by_user.get(self.user_id))
        return FakeQuery(all_result=self.agent_usage)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, models.UserSettings):
            if obj.id is None:
                obj.id = 1
            if obj.created_at is None:
                obj.created_at = datetime(2024, 1, 1)
            if obj.updated_at is None:
                obj.updated_at = datetime(2024, 1, 1)
            if obj.widget_theme is None:
                obj.widget_theme = "default"
            if obj.widget_color is None:
                obj.widget_color = "#4a6cf7"
            if obj.widget_position is None:
                obj.widget_position = "bottom-right"
            if obj.widget_size is None:
                obj.widget_size = "medium"
            if obj.email_notifications is None:
                obj.email_notifications = True
            if obj.browser_notifications is None:
                obj.browser_notifications = False
            if obj.notification_frequency is None:
                obj.notification_frequency = "immediate"
            if obj.default_language is None:
                obj.default_language = "en"
            if obj.response_style is None:
                obj.response_style = "professional"
            if obj.max_response_length is None:
                obj.max_response_length = "medium"
            if obj.auto_suggestions is None:
                obj.auto_suggestions = True
            if obj.data_retention_days is None:
                obj.data_retention_days = 30
            if obj.analytics_enabled is None:
                obj.analytics_enabled = True
            if obj.share_usage_data is None:
                obj.share_usage_data = False
            if obj.api_rate_limit_preference is None:
                obj.api_rate_limit_preference = "standard"
            if obj.debug_mode is None:
                obj.debug_mode = False
            self.settings_by_user[self.user_id] = obj

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def flush(self):
        return None

    def delete(self, obj):
        self.deleted.append(obj)
        if isinstance(obj, models.UserSettings):
            self.settings_by_user.pop(self.user_id, None)


def build_app():
    app = FastAPI()
    app.include_router(user_routes.router, prefix="/users")
    return app


def test_get_user_settings_creates_defaults():
    user = FakeUser(user_id=5)
    db = FakeDb(user_id=user.id)
    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.get("/users/settings")

    assert response.status_code == 200, "Expected settings endpoint to succeed"
    payload = response.json()
    assert payload["user_id"] == 5, (
        "Expected created settings to use current user_id"
    )
    assert payload["widget_theme"] == "default", (
        "Expected default widget_theme in created settings"
    )
    assert len(db.added) == 1, "Expected settings to be added to db"


def test_create_user_settings_returns_400_if_exists():
    user = FakeUser(user_id=6)
    db = FakeDb(user_id=user.id)
    existing = models.UserSettings(user_id=user.id)
    db.settings_by_user[user.id] = existing

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.post("/users/settings", json={"widget_theme": "dark"})

    assert response.status_code == 400, "Expected existing settings to return 400"
    assert response.json() == {
        "detail": "User settings already exist. Use PUT to update."
    }, "Expected existing settings detail message"


def test_update_user_settings_creates_when_missing():
    user = FakeUser(user_id=7)
    db = FakeDb(user_id=user.id)

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.put("/users/settings", json={"widget_color": "#000000"})

    assert response.status_code == 200, "Expected settings update to succeed"
    payload = response.json()
    assert payload["widget_color"] == "#000000", (
        "Expected widget_color to be updated"
    )
    assert payload["user_id"] == 7, "Expected settings to be tied to current user"


def test_delete_user_settings_returns_404_when_missing():
    user = FakeUser(user_id=8)
    db = FakeDb(user_id=user.id)

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.delete("/users/settings")

    assert response.status_code == 404, "Expected delete to fail when settings missing"
    assert response.json() == {"detail": "User settings not found"}, (
        "Expected missing settings detail message"
    )


def test_widget_config_defaults_when_missing():
    user = FakeUser(user_id=9)
    db = FakeDb(user_id=user.id)

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.get("/users/settings/widget-config")

    assert response.status_code == 200, "Expected widget-config to succeed"
    assert response.json() == {
        "theme": "default",
        "color": "#4a6cf7",
        "position": "bottom-right",
        "size": "medium",
        "language": "en",
        "auto_suggestions": True,
    }, "Expected widget-config defaults when settings missing"


def test_widget_config_uses_settings_when_present():
    user = FakeUser(user_id=10)
    db = FakeDb(user_id=user.id)
    settings = models.UserSettings(
        user_id=user.id,
        widget_theme="dark",
        widget_color="#123",
        widget_position="top-left",
        widget_size="small",
        default_language="es",
        auto_suggestions=False,
    )
    db.settings_by_user[user.id] = settings

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.get("/users/settings/widget-config")

    assert response.status_code == 200, "Expected widget-config to succeed"
    assert response.json() == {
        "theme": "dark",
        "color": "#123",
        "position": "top-left",
        "size": "small",
        "language": "es",
        "auto_suggestions": False,
    }, "Expected widget-config to reflect stored settings"


def test_reset_credits_requires_admin():
    user = FakeUser(user_id=11, user_type="free")
    db = FakeDb(user_id=user.id)

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.post("/users/reset-credits")

    assert response.status_code == 403, "Expected non-admin reset to be forbidden"
    assert response.json() == {
        "detail": "Forbidden: Admin access required"
    }, "Expected reset-credits to enforce admin access"


def test_reset_credits_updates_user_for_admin():
    user = FakeUser(user_id=12, user_type="admin")
    db = FakeDb(user_id=user.id)

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.post("/users/reset-credits")

    assert response.status_code == 200, "Expected admin reset to succeed"
    payload = response.json()
    assert payload["message"] == "Credits have been reset", (
        "Expected reset-credits to return success message"
    )
    assert payload["credits_remaining"] == 999999, (
        "Expected reset-credits to set credits_remaining to max"
    )
    assert "next_reset" in payload, "Expected next_reset to be returned"


def test_get_credit_info_includes_agent_usage():
    user = FakeUser(user_id=13, user_type="pro")
    agent_usage = [
        SimpleNamespace(id="a1", name="Agent One", total_used=5),
        SimpleNamespace(id="a2", name="Agent Two", total_used=None),
    ]
    db = FakeDb(user_id=user.id, agent_usage=agent_usage)

    app = build_app()
    app.dependency_overrides[user_routes.get_db] = lambda: db
    app.dependency_overrides[jwt.get_current_user] = lambda: user

    client = TestClient(app)
    response = client.get("/users/credits")

    assert response.status_code == 200, "Expected credits endpoint to succeed"
    payload = response.json()

    assert payload["user_type"] == "pro", "Expected user_type in credits payload"
    assert payload["credits_remaining"] == 12, "Expected credits_remaining in payload"
    assert payload["max_credits"] == 999999, "Expected max_credits from user"
    assert payload["agent_usage"] == [
        {"agent_id": "a1", "agent_name": "Agent One", "credits_used": 5},
        {"agent_id": "a2", "agent_name": "Agent Two", "credits_used": 0},
    ], "Expected agent usage breakdown with default credits_used=0"
