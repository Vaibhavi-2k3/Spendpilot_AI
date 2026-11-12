
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.main import app
from app.models.recommendation import Recommendation
from tests.test_database_config import get_test_database_url


def test_complete_recommendation_api_workflow():
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

            # SELECT starts an implicit transaction.
            connection.rollback()
            outer_transaction = connection.begin()

            def override_get_db():
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as db:
                    yield db

            app.dependency_overrides[get_db] = override_get_db

            try:
                with TestClient(app) as client:
                    # 1. Create a shopping session.
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
                        f"/api/shopping-sessions/"
                        f"{session_id}/discover"
                    )

                    recommendations_url = (
                        f"/api/shopping-sessions/"
                        f"{session_id}/recommendations"
                    )

                    # 2. Discover demo catalog products.
                    discover_response = client.post(
                        discover_url
                    )

                    assert discover_response.status_code == 200
                    assert len(discover_response.json()) == 3

                    # 3. Generate recommendations.
                    first_response = client.post(
                        recommendations_url
                    )

                    assert first_response.status_code == 200

                    first_recommendations = (
                        first_response.json()
                    )

                    assert len(first_recommendations) == 3

                    assert all(
                        item["shopping_session_id"] == session_id
                        for item in first_recommendations
                    )

                    assert all(
                        0 <= item["score"] <= 1
                        for item in first_recommendations
                    )

                    assert all(
                        item["reasoning"]
                        for item in first_recommendations
                    )

                    scores = [
                        item["score"]
                        for item in first_recommendations
                    ]

                    assert scores == sorted(
                        scores,
                        reverse=True,
                    )

                    first_ids = {
                        item["product_id"]: item["id"]
                        for item in first_recommendations
                    }

                    # 4. Retrieve saved recommendations.
                    get_response = client.get(
                        recommendations_url
                    )

                    assert get_response.status_code == 200

                    saved_recommendations = (
                        get_response.json()
                    )

                    assert len(saved_recommendations) == 3

                    saved_ids = {
                        item["product_id"]: item["id"]
                        for item in saved_recommendations
                    }

                    assert saved_ids == first_ids

                    saved_scores = [
                        item["score"]
                        for item in saved_recommendations
                    ]

                    assert saved_scores == sorted(
                        saved_scores,
                        reverse=True,
                    )

                    # 5. Generate again without duplicates.
                    second_response = client.post(
                        recommendations_url
                    )

                    assert second_response.status_code == 200

                    second_recommendations = (
                        second_response.json()
                    )

                    assert len(second_recommendations) == 3

                    second_ids = {
                        item["product_id"]: item["id"]
                        for item in second_recommendations
                    }

                    assert second_ids == first_ids

                    # 6. Confirm persisted row count.
                    with Session(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                    ) as db:
                        count = db.scalar(
                            select(func.count())
                            .select_from(Recommendation)
                            .where(
                                Recommendation.shopping_session_id
                                == session_id
                            )
                        )

                        assert count == 3

            finally:
                app.dependency_overrides.pop(
                    get_db,
                    None,
                )
                outer_transaction.rollback()

    finally:
        engine.dispose()
