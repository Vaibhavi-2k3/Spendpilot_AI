
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from tests.test_database_config import get_test_database_url


def test_complete_shopping_api_workflow():
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
                    create_response = client.post(
                        "/api/shopping-sessions",
                        json={
                            "query": "wireless headphones",
                            "budget_amount": 100,
                            "currency": "USD",
                        },
                    )

                    assert create_response.status_code == 201

                    session_id = create_response.json()["id"]

                    discover_url = (
                        f"/api/shopping-sessions/{session_id}/discover"
                    )

                    products_url = (
                        f"/api/shopping-sessions/{session_id}/products"
                    )

                    first_response = client.post(discover_url)

                    assert first_response.status_code == 200
                    assert len(first_response.json()) == 3

                    first_ids = {
                        product["id"]
                        for product in first_response.json()
                    }

                    products_response = client.get(products_url)

                    assert products_response.status_code == 200
                    assert len(products_response.json()) == 3

                    second_response = client.post(discover_url)

                    assert second_response.status_code == 200
                    assert len(second_response.json()) == 3

                    second_ids = {
                        product["id"]
                        for product in second_response.json()
                    }

                    assert first_ids == second_ids

            finally:
                app.dependency_overrides.pop(get_db, None)
                transaction.rollback()

    finally:
        engine.dispose()
