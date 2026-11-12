
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app


client = TestClient(app)


def test_list_products_empty():
    mock_db = MagicMock()
    mock_db.get.return_value = MagicMock()
    mock_db.scalars.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.get(
            "/api/shopping-sessions/test-session/products"
        )

        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_list_products_success():
    mock_db = MagicMock()
    mock_db.get.return_value = MagicMock()

    product = SimpleNamespace(
        id="test-product-123",
        shopping_session_id="test-session",
        name="Wireless Headphones",
        description="Noise-cancelling headphones",
        price=Decimal("79.99"),
        currency="USD",
        merchant="Demo Store",
        product_url="https://example.com/headphones",
        image_url=None,
        availability="in_stock",
        source_type="demo_catalog",
        created_at=datetime.now(timezone.utc),
    )

    mock_db.scalars.return_value.all.return_value = [product]

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.get(
            "/api/shopping-sessions/test-session/products"
        )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["name"] == "Wireless Headphones"
        assert Decimal(data[0]["price"]) == Decimal("79.99")
        assert data[0]["source_type"] == "demo_catalog"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_list_products_session_not_found():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        response = client.get(
            "/api/shopping-sessions/nonexistent-session/products"
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Shopping session not found"
        }
        mock_db.scalars.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
