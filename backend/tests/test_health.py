"""GET /health, per specs/001-repo-foundations/contracts/health.md (spec FR-003)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_and_nothing_else() -> None:
    """Fails if /health is missing, returns another status, isn't JSON, or adds any field."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}
