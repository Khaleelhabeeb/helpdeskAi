from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import models as models_routes
from utils import jwt


def build_app():
    app = FastAPI()
    app.include_router(models_routes.router, prefix="/models")
    return app


def test_available_models_route_returns_cached(monkeypatch):
    async def fake_get_json(_key):
        return [
            {
                "id": "groq/x",
                "label": "X",
                "provider": "groq",
                "logo": "groq",
                "locked": False,
            }
        ]

    monkeypatch.setattr(models_routes, "aredis_get_json", fake_get_json)

    app = build_app()
    app.dependency_overrides[models_routes.get_current_user] = lambda: object()

    client = TestClient(app)
    response = client.get("/models/available")

    assert response.status_code == 200, "Expected available models to succeed"
    assert response.json() == {
        "models": [
            {
                "id": "groq/x",
                "label": "X",
                "provider": "groq",
                "logo": "groq",
                "locked": False,
            }
        ]
    }, "Expected cached models payload"
