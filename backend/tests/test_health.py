
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "SpendPilot AI API"


def test_readiness_when_database_connected():
    mock_connection = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_connection

    with patch("app.main.engine.connect", return_value=mock_context):
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "connected",
    }


def test_readiness_when_database_unavailable():
    error = OperationalError(
        "SELECT 1",
        {},
        Exception("Connection failed"),
    )

    with patch("app.main.engine.connect", side_effect=error):
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
