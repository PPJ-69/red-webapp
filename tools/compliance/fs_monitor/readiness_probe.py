from fastapi.testclient import TestClient

from backend.app.main import app


with TestClient(app) as client:
    assert client.get("/health/ready").status_code == 200
