
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.models.shopping_session import ShoppingSession
from app.services.product_discovery import DiscoveryContextChanged


client = TestClient(app)


def make_session():
    return ShoppingSession(
        id="test-session-id",
        query="wireless headphones",
        budget_amount=100,
        currency="USD",
        status="created",
    )


def test_discovery_session_not_found():
    db = MagicMock()
    db.get.return_value = None

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post(
            "/api/shopping-sessions/missing-session/discover"
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Shopping session not found"
        }
    finally:
        app.dependency_overrides.clear()


def test_discovery_returns_empty_results():
    db = MagicMock()
    db.get.return_value = make_session()
    db.scalars.return_value.all.return_value = []

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.products.discover_products",
            return_value=[],
        ) as mock_discover:
            response = client.post(
                "/api/shopping-sessions/test-session-id/discover"
            )

        assert response.status_code == 200
        assert response.json() == []
        mock_discover.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


def test_discovery_returns_products():
    db = MagicMock()
    db.get.return_value = make_session()

    product = MagicMock()
    product.id = "product-123"
    product.shopping_session_id = "test-session-id"
    product.name = "Wireless Noise Cancelling Headphones"
    product.description = "Bluetooth headphones"
    product.price = "79.99"
    product.currency = "USD"
    product.merchant = "SpendPilot Demo Store"
    product.product_url = "https://example.com/demo/headphones"
    product.image_url = None
    product.availability = "in_stock"
    product.source_type = "demo_catalog"

    from datetime import datetime, timezone

    product.created_at = datetime.now(timezone.utc)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with patch(
            "app.api.routes.products.discover_products",
            return_value=[product],
        ):
            response = client.post(
                "/api/shopping-sessions/test-session-id/discover"
            )

        assert response.status_code == 200

        data = response.json()

        assert len(data) == 1
        assert data[0]["name"] == (
            "Wireless Noise Cancelling Headphones"
        )
        assert data[0]["price"] == "79.99"
        assert data[0]["source_type"] == "demo_catalog"
    finally:
        app.dependency_overrides.clear()


def test_discovery_returns_conflict_when_intent_changes_during_search():
    db = MagicMock()
    db.get.return_value = make_session()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with patch(
            "app.api.routes.products.discover_products",
            side_effect=DiscoveryContextChanged("Shopping intent changed. Retry discovery."),
        ):
            response = client.post("/api/shopping-sessions/test-session-id/discover")
        assert response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)
