from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app


def test_generate_recommendations_session_not_found():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/shopping-sessions/missing-session/recommendations"
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Shopping session not found"
        }
        mock_db.get.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_list_recommendations_session_not_found():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/shopping-sessions/missing-session/recommendations"
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Shopping session not found"
        }
        mock_db.get.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_generate_recommendations_success():
    session_id = "test-session-123"

    mock_db = MagicMock()
    mock_session = SimpleNamespace(id=session_id)
    mock_db.get.return_value = mock_session

    mock_recommendation = SimpleNamespace(
        id="recommendation-123",
        shopping_session_id=session_id,
        product_id="product-123",
        score=0.875,
        reasoning="Matches search terms and fits the budget.",
        created_at=datetime(
            2026, 1, 1, tzinfo=timezone.utc
        ),
    )

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.api.routes.recommendations.generate_recommendations",
            return_value=[mock_recommendation],
        ) as mock_generate:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/shopping-sessions/{session_id}/recommendations"
                )

            assert response.status_code == 200

            data = response.json()

            assert len(data) == 1
            assert data[0]["id"] == "recommendation-123"
            assert data[0]["shopping_session_id"] == session_id
            assert data[0]["product_id"] == "product-123"
            assert data[0]["score"] == 0.875
            assert data[0]["reasoning"] == (
                "Matches search terms and fits the budget."
            )
            assert data[0]["created_at"] is not None

            mock_generate.assert_called_once_with(
                shopping_session=mock_session,
                db=mock_db,
            )

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_list_recommendations_success():
    session_id = "test-session-123"

    mock_db = MagicMock()
    mock_session = SimpleNamespace(id=session_id)
    mock_db.get.return_value = mock_session

    recommendation_1 = SimpleNamespace(
        id="recommendation-1",
        shopping_session_id=session_id,
        product_id="product-1",
        score=0.95,
        reasoning="Highly relevant product.",
        created_at=datetime(
            2026, 1, 1, tzinfo=timezone.utc
        ),
    )

    recommendation_2 = SimpleNamespace(
        id="recommendation-2",
        shopping_session_id=session_id,
        product_id="product-2",
        score=0.75,
        reasoning="Good alternative.",
        created_at=datetime(
            2026, 1, 1, tzinfo=timezone.utc
        ),
    )

    mock_db.scalars.return_value.all.return_value = [
        recommendation_1,
        recommendation_2,
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/shopping-sessions/{session_id}/recommendations"
            )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 2

        assert data[0]["id"] == "recommendation-1"
        assert data[0]["score"] == 0.95

        assert data[1]["id"] == "recommendation-2"
        assert data[1]["score"] == 0.75

        mock_db.scalars.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_db, None)
