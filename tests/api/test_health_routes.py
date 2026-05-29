from fastapi import FastAPI
from fastapi.testclient import TestClient


def build_app():
    app = FastAPI()

    @app.get("/health")
    @app.get("/healthz")
    def health_check():
        return {"status": "ok"}

    return app


def test_health_endpoints_return_ok():
    client = TestClient(build_app())

    response = client.get("/health")
    assert response.status_code == 200, "Expected /health to succeed"
    assert response.json() == {"status": "ok"}, "Expected /health to return ok"

    response = client.get("/healthz")
    assert response.status_code == 200, "Expected /healthz to succeed"
    assert response.json() == {"status": "ok"}, "Expected /healthz to return ok"
