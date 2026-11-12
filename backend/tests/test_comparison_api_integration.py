
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.models.product import Product
from app.models.shopping_session import ShoppingSession
from app.services.recommendation_service import generate_recommendations
from tests.test_database_config import get_test_database_url


def test_comparison_api_with_demo_and_external_products():
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
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    shopping_session = ShoppingSession(
                        query="wireless headphones",
                        budget_amount=5000,
                        currency="INR",
                        status="created",
                    )

                    db.add(shopping_session)
                    db.flush()

                    demo_product = Product(
                        shopping_session_id=shopping_session.id,
                        name="Wireless Headphones Demo",
                        description="Demo headphones",
                        price=Decimal("1999.00"),
                        currency="INR",
                        merchant="SpendPilot Demo Store",
                        product_url="https://example.com/demo/headphones",
                        image_url=None,
                        availability="in_stock",
                        source_type="demo_catalog",
                    )

                    external_product = Product(
                        shopping_session_id=shopping_session.id,
                        name="Wireless Headphones External",
                        description="Bluetooth headphones",
                        price=Decimal("999.00"),
                        currency="INR",
                        merchant="External Merchant",
                        product_url="https://www.google.com/search?q=headphones",
                        image_url=None,
                        availability="unknown",
                        source_type="serpapi_google_shopping",
                    )

                    db.add_all([
                        demo_product,
                        external_product,
                    ])
                    db.commit()

                    session_id = shopping_session.id

                    generated = generate_recommendations(
                        shopping_session,
                        db,
                    )

                    assert len(generated) == 2

                with TestClient(app) as client:
                    url = (
                        f"/api/shopping-sessions/"
                        f"{session_id}/comparison"
                    )

                    first_response = client.get(url)

                    assert first_response.status_code == 200

                    first = first_response.json()

                    assert len(first) == 2

                    scores = [
                        item["score"]
                        for item in first
                    ]

                    assert scores == sorted(
                        scores,
                        reverse=True,
                    )

                    by_source = {
                        item["source_type"]: item
                        for item in first
                    }

                    demo = by_source["demo_catalog"]

                    assert demo["checkout_eligible"] is True
                    assert demo["link_type"] == "demo_product"
                    assert demo["availability"] == "in_stock"

                    external = by_source[
                        "serpapi_google_shopping"
                    ]

                    assert external["checkout_eligible"] is False
                    assert external["link_type"] == "shopping_discovery"
                    assert external["availability"] == "unknown"
                    assert "comparison only" in external["reasoning"]

                    for item in first:
                        assert item["shopping_session_id"] == session_id
                        assert item["recommendation_id"]
                        assert item["product_id"]
                        assert item["name"]
                        assert item["merchant"]
                        assert item["price"]
                        assert item["currency"] == "INR"

                    second_response = client.get(url)

                    assert second_response.status_code == 200

                    second = second_response.json()

                    first_ids = {
                        item["product_id"]: item["recommendation_id"]
                        for item in first
                    }

                    second_ids = {
                        item["product_id"]: item["recommendation_id"]
                        for item in second
                    }

                    assert first_ids == second_ids

            finally:
                app.dependency_overrides.pop(get_db, None)
                transaction.rollback()

    finally:
        engine.dispose()


def test_comparison_api_session_not_found():
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
                with TestClient(app) as client:
                    response = client.get(
                        "/api/shopping-sessions/"
                        "00000000-0000-0000-0000-000000000000/"
                        "comparison"
                    )

                assert response.status_code == 404
                assert response.json() == {
                    "detail": "Shopping session not found"
                }

            finally:
                app.dependency_overrides.pop(get_db, None)
                transaction.rollback()

    finally:
        engine.dispose()
