
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.providers.base import DiscoveredProduct
from tests.test_database_config import get_test_database_url


@pytest.fixture
def client():
    engine = create_engine(
        get_test_database_url(),
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            database_name = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()

            assert database_name == "spendpilot_test_db"

            connection.rollback()
            transaction = connection.begin()

            def override_get_db():
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    yield db

            app.dependency_overrides[get_db] = override_get_db

            try:
                with TestClient(app) as test_client:
                    yield test_client
            finally:
                app.dependency_overrides.pop(get_db, None)
                transaction.rollback()
    finally:
        engine.dispose()


def create_session(
    client,
    currency="USD",
    budget_amount=100,
):
    response = client.post(
        "/api/shopping-sessions",
        json={
            "query": "wireless headphones",
            "budget_amount": budget_amount,
            "currency": currency,
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def make_external_product(
    currency="USD",
    price="79.99",
):
    return DiscoveredProduct(
        name="Wireless Headphones",
        description="Bluetooth headphones",
        price=Decimal(price),
        currency=currency,
        merchant="Example Electronics",
        product_url=(
            "https://example.com/shopping/headphones"
        ),
        image_url=(
            "https://example.com/headphones.jpg"
        ),
        availability="unknown",
        source_type="serpapi_google_shopping",
    )


@pytest.mark.parametrize(
    "currency,budget,price",
    [
        ("USD", 100, "79.99"),
        ("INR", 5000, "2890"),
    ],
)
def test_serpapi_discovery_saves_products(
    client,
    currency,
    budget,
    price,
):
    session_id = create_session(
        client,
        currency=currency,
        budget_amount=budget,
    )

    mock_search = AsyncMock(
        return_value=[
            make_external_product(
                currency=currency,
                price=price,
            )
        ]
    )

    with (
        patch(
            "app.api.routes.products.get_settings",
            return_value=SimpleNamespace(
                serpapi_api_key="test-api-key"
            ),
        ),
        patch(
            "app.api.routes.products.SerpApiProvider.search",
            new=mock_search,
        ),
    ):
        response = client.post(
            f"/api/shopping-sessions/{session_id}"
            "/discover?source=serpapi"
        )

    assert response.status_code == 200

    products = response.json()
    assert len(products) == 1

    product = products[0]

    assert product["name"] == "Wireless Headphones"
    assert Decimal(product["price"]) == Decimal(price)
    assert product["currency"] == currency
    assert product["merchant"] == "Example Electronics"
    assert product["availability"] == "unknown"
    assert product["source_type"] == (
        "serpapi_google_shopping"
    )

    mock_search.assert_awaited_once_with(
        query="wireless headphones",
        budget_amount=budget,
        currency=currency,
    )

    saved_response = client.get(
        f"/api/shopping-sessions/{session_id}/products"
    )

    assert saved_response.status_code == 200
    saved_products = saved_response.json()

    assert len(saved_products) == 1
    assert saved_products[0]["id"] == product["id"]


def test_serpapi_discovery_prevents_duplicates(client):
    session_id = create_session(client)

    mock_search = AsyncMock(
        return_value=[make_external_product()]
    )

    with (
        patch(
            "app.api.routes.products.get_settings",
            return_value=SimpleNamespace(
                serpapi_api_key="test-api-key"
            ),
        ),
        patch(
            "app.api.routes.products.SerpApiProvider.search",
            new=mock_search,
        ),
    ):
        url = (
            f"/api/shopping-sessions/{session_id}"
            "/discover?source=serpapi"
        )

        first_response = client.post(url)
        second_response = client.post(url)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_products = first_response.json()
    second_products = second_response.json()

    assert len(first_products) == 1
    assert len(second_products) == 1

    assert first_products[0]["id"] == (
        second_products[0]["id"]
    )

    assert mock_search.await_count == 2

    saved_response = client.get(
        f"/api/shopping-sessions/{session_id}/products"
    )

    assert saved_response.status_code == 200
    assert len(saved_response.json()) == 1


def test_default_discovery_uses_demo_catalog(client):
    session_id = create_session(client)

    with patch(
        "app.api.routes.products.SerpApiProvider.search",
        new_callable=AsyncMock,
    ) as mock_search:
        response = client.post(
            f"/api/shopping-sessions/{session_id}/discover"
        )

    assert response.status_code == 200

    products = response.json()

    assert len(products) > 0

    assert all(
        product["source_type"] == "demo_catalog"
        for product in products
    )

    mock_search.assert_not_awaited()


def test_serpapi_missing_api_key(client):
    session_id = create_session(client)

    with patch(
        "app.api.routes.products.get_settings",
        return_value=SimpleNamespace(
            serpapi_api_key=None
        ),
    ):
        response = client.post(
            f"/api/shopping-sessions/{session_id}"
            "/discover?source=serpapi"
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Live product discovery is not configured"
        )
    }


def test_serpapi_provider_error_is_safe(client):
    session_id = create_session(client)

    mock_search = AsyncMock(
        side_effect=ValueError(
            "SerpApi request failed with HTTP status 503"
        )
    )

    with (
        patch(
            "app.api.routes.products.get_settings",
            return_value=SimpleNamespace(
                serpapi_api_key="test-api-key"
            ),
        ),
        patch(
            "app.api.routes.products.SerpApiProvider.search",
            new=mock_search,
        ),
    ):
        response = client.post(
            f"/api/shopping-sessions/{session_id}"
            "/discover?source=serpapi"
        )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "Live product discovery is temporarily unavailable"
        )
    }

    assert "test-api-key" not in response.text


def test_invalid_discovery_source(client):
    session_id = create_session(client)

    response = client.post(
        f"/api/shopping-sessions/{session_id}"
        "/discover?source=invalid"
    )

    assert response.status_code == 422
