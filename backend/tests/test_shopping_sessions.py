
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db
from app.models.shopping_session import ShoppingSession


client = TestClient(app)


def test_create_shopping_session():
    mock_db = MagicMock()

    def fake_refresh(session):
        session.id = "test-session-123"
        session.status = "created"
        from datetime import datetime, timezone
        session.created_at = datetime.now(timezone.utc)

    mock_db.refresh.side_effect = fake_refresh

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.post(
            "/api/shopping-sessions",
            json={
                "query": "Best wireless headphones",
                "budget_amount": 100,
                "currency": "USD",
            },
        )

        assert response.status_code == 201
        assert response.json()["query"] == "Best wireless headphones"
        assert response.json()["budget_amount"] == 100
        assert response.json()["status"] == "created"

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_get_shopping_session_not_found():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.get(
            "/api/shopping-sessions/nonexistent-session"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Shopping session not found"
    finally:
        app.dependency_overrides.clear()


def test_create_shopping_session_invalid_budget():
    response = client.post(
        "/api/shopping-sessions",
        json={
            "query": "Headphones",
            "budget_amount": -50,
            "currency": "USD",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"query": " \t\n "},
        {"query": "x" * 2001},
        {"currency": "EUR"},
        {"budget_amount": 2_147_483_648},
        {"budget_amount": 10.5},
        {"budget_amount": True},
        {"budget_amount": "100"},
    ],
)
def test_invalid_session_input_does_not_write(overrides):
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/api/shopping-sessions",
            json={
                "query": "headphones", "currency": "USD",
                "budget_amount": 100, **overrides,
            },
        )
        assert response.status_code == 422
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_query_is_trimmed_before_storage():
    from app.schemas.shopping_session import ShoppingSessionCreate

    payload = ShoppingSessionCreate(query="  wireless headphones  ")
    assert payload.query == "wireless headphones"
